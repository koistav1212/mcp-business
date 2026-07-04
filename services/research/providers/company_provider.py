"""
Multi-source company profile provider.

Sources (in priority order):
  1. SEC EDGAR company_facts → official filings (highest authority)
  2. Wikipedia infobox + summary → factual identity layer
  3. yfinance longBusinessSummary + companyOfficers → live supplement
  4. Crunchbase public search → funding + founding + employee signals
  5. LinkedIn public company page (organic scrape, no API key needed)
  6. SimilarWeb public stats → web presence signal

Returns List[ResearchEvidence] — every fact carries its source and confidence.
"""

import re
import json
import asyncio
import logging
import httpx
import yfinance as yf
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from services.research.base import BaseProvider
from services.knowledge.evidence import ResearchEvidence
from services.knowledge.citation_manager import CitationManager

logger = logging.getLogger("uvicorn.error")

# ─── Wikipedia wikitext helpers (unchanged from your original, they work well) ──

def _resolve_templates(text: str) -> str:
    for _ in range(40):
        m = re.search(r"\{\{([^{}]+)\}\}", text)
        if not m:
            break
        tc = m.group(1)
        parts = tc.split("|")
        name = parts[0].strip().lower()
        args = parts[1:]
        if name in ("url", "website"):
            resolved = args[0].strip() if args else ""
        elif name in ("unbulleted list", "plainlist", "flatlist", "bulleted list"):
            valid = [a.strip().lstrip("*").strip() for a in args if a.strip() and "=" not in a]
            resolved = ", ".join(valid)
        elif "date" in name:
            nums = [a.strip() for a in args if a.strip().isdigit()]
            resolved = "-".join(nums) if nums else ""
        else:
            valid = [a.strip() for a in args if "=" not in a]
            resolved = valid[0] if valid else ""
        text = text[: m.start()] + resolved + text[m.end() :]
    return text


def _clean_wiki_val(val: str) -> str:
    val = _resolve_templates(val)
    val = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", val)
    val = re.sub(r"\[\[([^\]]+)\]\]", r"\1", val)
    val = re.sub(r"<!--.*?-->", "", val, flags=re.DOTALL)
    val = re.sub(r"<[^>]+>", "", val)
    val = val.replace("|", ",").replace("*", ",").replace("\n", ", ")
    val = re.sub(r"\s+", " ", val)
    val = re.sub(r",\s*,", ",", val)
    return val.strip(", ")


def _extract_infobox(wikitext: str) -> Dict[str, str]:
    m = re.search(r"\{\{[Ii]nfobox company", wikitext)
    if not m:
        return {}
    start = m.start()
    depth, end = 0, -1
    for i in range(start, len(wikitext)):
        if wikitext[i : i + 2] == "{{":
            depth += 1
        elif wikitext[i : i + 2] == "}}":
            depth -= 1
            if depth == 0:
                end = i + 2
                break
    if end == -1:
        return {}
    content = wikitext[m.end() : end - 2].strip()
    parts, cur, bl, sl = [], [], 0, 0
    i = 0
    while i < len(content):
        if content[i : i + 2] == "{{":
            bl += 1; cur.append("{{"); i += 2; continue
        elif content[i : i + 2] == "}}":
            bl -= 1; cur.append("}}"); i += 2; continue
        elif content[i : i + 2] == "[[":
            sl += 1; cur.append("[["); i += 2; continue
        elif content[i : i + 2] == "]]":
            sl -= 1; cur.append("]]"); i += 2; continue
        if content[i] == "|" and bl == 0 and sl == 0:
            parts.append("".join(cur).strip()); cur = []
        else:
            cur.append(content[i])
        i += 1
    if cur:
        parts.append("".join(cur).strip())
    fields = {}
    for part in parts:
        if "=" in part:
            k, v = part.split("=", 1)
            fields[k.strip()] = _clean_wiki_val(v.strip())
    return fields


# ─── Common HTTP helper ─────────────────────────────────────────────────────

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

_BOT_HEADERS = {
    "User-Agent": "MCPBusinessIntelligenceBot/1.0 (contact@mcp-business.com)"
}

async def _get(client: httpx.AsyncClient, url: str, **kw) -> Optional[httpx.Response]:
    try:
        r = await client.get(url, timeout=12.0, **kw)
        if r.status_code == 200:
            return r
    except Exception as exc:
        logger.debug(f"GET {url} failed: {exc}")
    return None


# ────────────────────────────────────────────────────────────────────────────


class CompanyProvider(BaseProvider):
    """
    Multi-source company profile provider.
    
    Parallel fetch strategy:
      Layer 1 (identity):  Wikipedia + yfinance  → always run
      Layer 2 (supplement): Crunchbase + SimilarWeb → run concurrently
      Layer 3 (people):   yfinance companyOfficers + Wikipedia key_people
    
    All facts are emitted as ResearchEvidence with per-fact confidence and source.
    """

    # ── Source 1: Wikipedia ─────────────────────────────────────────────────

    async def _fetch_wikipedia(
        self, client: httpx.AsyncClient, company: str
    ) -> Dict[str, Any]:
        """Returns dict with keys: name, overview, headquarters, founders,
        employee_count, website, leadership, wiki_url."""
        out: Dict[str, Any] = {}
        search_url = "https://en.wikipedia.org/w/api.php"
        r = await _get(
            client, search_url,
            params={"action": "query", "list": "search",
                    "srsearch": company, "format": "json"},
            headers=_BOT_HEADERS,
        )
        if not r:
            return out
        items = r.json().get("query", {}).get("search", [])
        if not items:
            return out
        title = items[0]["title"]
        out["wiki_url"] = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"

        # Infobox
        r2 = await _get(
            client, search_url,
            params={"action": "query", "prop": "revisions",
                    "rvprop": "content", "rvsection": 0,
                    "titles": title, "format": "json"},
            headers=_BOT_HEADERS,
        )
        if r2:
            pages = r2.json().get("query", {}).get("pages", {})
            for page in pages.values():
                revs = page.get("revisions", [])
                if revs:
                    wikitext = revs[0].get("*", "")
                    infobox = _extract_infobox(wikitext)
                    if infobox:
                        if infobox.get("name"):
                            out["name"] = infobox["name"]
                        hq_parts = [
                            infobox.get("hq_location_city"),
                            infobox.get("hq_location_country")
                            or infobox.get("hq_location")
                            or infobox.get("location"),
                        ]
                        hq = ", ".join(p for p in hq_parts if p)
                        if hq:
                            out["headquarters"] = hq
                        if infobox.get("website"):
                            out["website"] = infobox["website"]
                        f_str = infobox.get("founders") or infobox.get("founder", "")
                        if f_str:
                            out["founders"] = [x.strip() for x in f_str.split(",") if x.strip()]
                        kp = infobox.get("key_people") or infobox.get("leadership", "")
                        leaders = []
                        for p in kp.split(","):
                            pc = p.strip()
                            if not pc:
                                continue
                            rm = re.match(r"(.*?)\((.*?)\)", pc)
                            if rm:
                                leaders.append({"name": rm.group(1).strip(), "role": rm.group(2).strip()})
                            else:
                                leaders.append({"name": pc, "role": "Executive"})
                        if leaders:
                            out["leadership"] = leaders
                        emp_str = infobox.get("num_employees") or infobox.get("num_members", "")
                        digits = "".join(re.findall(r"\d+", emp_str.split("(")[0].replace(",", "")))
                        if digits:
                            out["employee_count"] = int(digits)

        # Summary (plain-text overview)
        r3 = await _get(
            client,
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}",
            headers=_BOT_HEADERS,
        )
        if r3:
            out["overview"] = r3.json().get("extract", "")[:800]

        return out

    # ── Source 2: yfinance supplement ──────────────────────────────────────

    async def _fetch_yfinance(
        self, ticker_symbol: Optional[str], company: str
    ) -> Dict[str, Any]:
        """Fetches live yfinance data in a thread to avoid blocking the event loop."""
        if not ticker_symbol:
            ticker_symbol = await self._resolve_ticker_yf(company)
        if not ticker_symbol:
            return {}
        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None, lambda: yf.Ticker(ticker_symbol).info
            )
            return {
                "ticker": ticker_symbol,
                "long_name": info.get("longName", ""),
                "overview": info.get("longBusinessSummary", ""),
                "website": info.get("website", ""),
                "headquarters": ", ".join(
                    filter(None, [info.get("city"), info.get("state"), info.get("country")])
                ),
                "employee_count": info.get("fullTimeEmployees"),
                "sector": info.get("sector", ""),
                "industry": info.get("industry", ""),
                "officers": [
                    {"name": o.get("name", ""), "role": o.get("title", "")}
                    for o in info.get("companyOfficers", [])[:8]
                    if o.get("name")
                ],
                "description": info.get("longBusinessSummary", ""),
            }
        except Exception as exc:
            logger.debug(f"yfinance fetch failed for {ticker_symbol}: {exc}")
            return {}

    async def _resolve_ticker_yf(self, company: str) -> Optional[str]:
        url = "https://query1.finance.yahoo.com/v1/finance/search"
        try:
            async with httpx.AsyncClient() as c:
                r = await c.get(
                    url,
                    params={"q": company, "quotesCount": 10, "newsCount": 0},
                    headers=_BROWSER_HEADERS,
                    timeout=8.0,
                )
                if r.status_code == 200:
                    for q in r.json().get("quotes", []):
                        if q.get("quoteType", "").upper() == "EQUITY":
                            return q.get("symbol")
        except Exception:
            pass
        return None

    # ── Source 3: Crunchbase public search ─────────────────────────────────

    async def _fetch_crunchbase(
        self, client: httpx.AsyncClient, company: str
    ) -> Dict[str, Any]:
        """
        Crunchbase public search page — no API key needed.
        Scrapes the JSON-LD and meta tags from their organisation search results.
        Returns funding_total, last_round, founded_year, employee_range.
        """
        slug = company.lower().replace(" ", "-").replace(",", "").replace(".", "")
        url = f"https://www.crunchbase.com/organization/{slug}"
        r = await _get(client, url, headers=_BROWSER_HEADERS)
        if not r:
            # Try search endpoint
            search_url = f"https://www.crunchbase.com/autocomplete?q={company}&limit=5"
            r = await _get(client, search_url, headers=_BROWSER_HEADERS)
            if not r:
                return {}
            try:
                results = r.json()
                entities = results.get("entities", [])
                if entities:
                    slug = entities[0].get("identifier", {}).get("permalink", slug)
                    url = f"https://www.crunchbase.com/organization/{slug}"
                    r = await _get(client, url, headers=_BROWSER_HEADERS)
            except Exception:
                return {}

        if not r:
            return {}

        html = r.text
        out: Dict[str, Any] = {}

        # Extract JSON-LD if present
        ld_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
        if ld_match:
            try:
                ld = json.loads(ld_match.group(1))
                out["founded_year"] = ld.get("foundingDate")
                if ld.get("numberOfEmployees"):
                    out["employee_range"] = str(ld["numberOfEmployees"])
                out["description"] = ld.get("description", "")[:400]
            except Exception:
                pass

        # Funding total from meta description
        funding_match = re.search(
            r"raised a total of (\$[\d.,]+[BMK]?)", html, re.IGNORECASE
        )
        if funding_match:
            out["funding_total"] = funding_match.group(1)

        # Last round
        round_match = re.search(
            r"(Series [A-Z]|Seed|Pre-Seed|IPO|Series [A-Z]\d?)[\s\S]{0,60}?(\$[\d.,]+[BMK]?)",
            html,
        )
        if round_match:
            out["last_round"] = f"{round_match.group(1)} {round_match.group(2)}"

        return out

    # ── Source 4: SimilarWeb public signal ─────────────────────────────────

    async def _fetch_similarweb(
        self, client: httpx.AsyncClient, website: str
    ) -> Dict[str, Any]:
        """
        SimilarWeb public overview page — no API key.
        Extracts monthly visits, global rank, top countries.
        """
        if not website:
            return {}
        domain = re.sub(r"https?://", "", website).rstrip("/").lstrip("www.")
        url = f"https://www.similarweb.com/website/{domain}/"
        r = await _get(client, url, headers=_BROWSER_HEADERS)
        if not r:
            return {}
        html = r.text
        out: Dict[str, Any] = {}

        # Monthly visits
        visit_match = re.search(
            r'"totalVisits":\s*"?([\d.]+[KMB]?)"?', html
        ) or re.search(r"([\d.]+[KMB]?)\s*Total Visits", html)
        if visit_match:
            out["monthly_visits"] = visit_match.group(1)

        # Global rank
        rank_match = re.search(r'"globalRank":\s*(\d+)', html) or re.search(
            r"Global Rank[\s\S]{0,30}?#?([\d,]+)", html
        )
        if rank_match:
            out["global_rank"] = rank_match.group(1).replace(",", "")

        return out

    # ── Source 5: LinkedIn public company page ──────────────────────────────

    async def _fetch_linkedin(
        self, client: httpx.AsyncClient, company: str
    ) -> Dict[str, Any]:
        """
        Fetches LinkedIn public company page (no auth required for basic metadata).
        Extracts: description, industry, company size, specialties, headquarters.
        """
        # Use LinkedIn's organic search to find the company slug first
        search_url = f"https://www.linkedin.com/company/{company.lower().replace(' ', '-')}/"
        r = await _get(client, search_url, headers=_BROWSER_HEADERS)
        if not r:
            # Try with LinkedIn search
            search_url = f"https://www.linkedin.com/search/results/companies/?keywords={company}"
            r = await _get(client, search_url, headers=_BROWSER_HEADERS)
            if not r:
                return {}
        html = r.text
        out: Dict[str, Any] = {}

        # JSON-LD structured data
        ld_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
        if ld_match:
            try:
                ld = json.loads(ld_match.group(1))
                if isinstance(ld, list):
                    ld = ld[0]
                out["description"] = ld.get("description", "")[:400]
                out["employee_range"] = str(ld.get("numberOfEmployees", {}).get("minValue", ""))
                out["specialties"] = ld.get("areaServed", "")
            except Exception:
                pass

        # Meta description fallback
        meta_match = re.search(r'<meta name="description" content="([^"]+)"', html)
        if meta_match and not out.get("description"):
            out["description"] = meta_match.group(1)[:300]

        # Industry signal from page text
        ind_match = re.search(r"Industry\s*<[^>]+>\s*([^<]{3,60})", html)
        if ind_match:
            out["industry"] = ind_match.group(1).strip()

        return out

    # ── Competitor enrichment ───────────────────────────────────────────────

    _INDUSTRY_PEERS: Dict[str, List[Dict[str, str]]] = {
        "Semiconductors": [
            {"name": "AMD", "website": "https://amd.com", "segment": "AI GPUs & CPUs"},
            {"name": "Intel", "website": "https://intel.com", "segment": "Processors & Foundry"},
            {"name": "Qualcomm", "website": "https://qualcomm.com", "segment": "Mobile & Wireless"},
            {"name": "Broadcom", "website": "https://broadcom.com", "segment": "Networking ASICs"},
        ],
        "Software—Application": [
            {"name": "Salesforce", "website": "https://salesforce.com", "segment": "CRM & Enterprise SaaS"},
            {"name": "Oracle", "website": "https://oracle.com", "segment": "Database & Cloud"},
            {"name": "Adobe", "website": "https://adobe.com", "segment": "Creative & Marketing"},
            {"name": "SAP", "website": "https://sap.com", "segment": "ERP & Enterprise"},
        ],
        "Software—Infrastructure": [
            {"name": "Microsoft", "website": "https://microsoft.com", "segment": "Cloud & OS"},
            {"name": "Amazon Web Services", "website": "https://aws.amazon.com", "segment": "Cloud Infrastructure"},
            {"name": "Google Cloud", "website": "https://cloud.google.com", "segment": "Cloud Platform"},
        ],
        "Internet Content & Information": [
            {"name": "Alphabet", "website": "https://google.com", "segment": "Search & Ads"},
            {"name": "Meta Platforms", "website": "https://meta.com", "segment": "Social Media & AI"},
            {"name": "ByteDance", "website": "https://bytedance.com", "segment": "Short Video & Social"},
        ],
        "Financial Services": [
            {"name": "Stripe", "website": "https://stripe.com", "segment": "Payments Infrastructure"},
            {"name": "PayPal", "website": "https://paypal.com", "segment": "Digital Payments"},
            {"name": "Square", "website": "https://squareup.com", "segment": "SMB Financial Services"},
        ],
        "Auto Manufacturers": [
            {"name": "Tesla", "website": "https://tesla.com", "segment": "Electric Vehicles & AI"},
            {"name": "Toyota", "website": "https://toyota.com", "segment": "Mass-Market ICE & Hybrid"},
            {"name": "BYD", "website": "https://byd.com", "segment": "EV & Battery"},
        ],
        "Biotechnology": [
            {"name": "Moderna", "website": "https://modernatx.com", "segment": "mRNA Therapeutics"},
            {"name": "BioNTech", "website": "https://biontech.com", "segment": "mRNA Oncology & Vaccines"},
            {"name": "Regeneron", "website": "https://regeneron.com", "segment": "Large Molecule Biologics"},
        ],
    }

    def _get_competitors(self, industry: str, sector: str) -> List[Dict[str, str]]:
        peers = self._INDUSTRY_PEERS.get(industry) or self._INDUSTRY_PEERS.get(sector, [])
        return peers[:4]

    async def _crawl_official_site(
        self, client: httpx.AsyncClient, website: str
    ) -> Dict[str, Any]:
        """
        One-hop crawl of the company's homepage to discover official pages
        (about, products/services/solutions, careers, contact, investors)
        and social profiles. Uses BeautifulSoup + httpx.
        """
        if not website:
            return {}

        # Normalize base URL
        base = website.strip()
        if not base.startswith(("http://", "https://")):
            base = "https://" + base
        # Drop trailing slashes for consistency
        base = base.rstrip("/")

        r = await _get(client, base, headers=_BROWSER_HEADERS)
        if not r:
            return {}

        html = r.text
        soup = BeautifulSoup(html, "html.parser")

        # Collect all anchors
        links = soup.find_all("a", href=True)

        official_pages: Dict[str, str] = {}
        products: List[Dict[str, str]] = []
        services: List[str] = []
        solutions_list: List[str] = []
        social_profiles: Dict[str, str] = {}
        contact_page: Optional[str] = None

        # Simple keyword patterns
        def norm(text: str) -> str:
            return text.strip().lower()

        for a in links:
            text = (a.get_text() or "").strip()
            href = a["href"].strip()
            if not text and not href:
                continue

            # Resolve relative URLs
            full_url = urljoin(base + "/", href)

            # Skip obvious junk like mailto, tel, javascript
            if href.startswith(("mailto:", "tel:", "javascript:")):
                continue

            t_norm = norm(text)
            h_norm = norm(href)

            # About / Company
            if any(k in t_norm for k in ["about", "who we are", "our company"]) or "about" in h_norm:
                official_pages.setdefault("about", full_url)

            # Careers / Jobs
            if any(k in t_norm for k in ["careers", "jobs", "join us"]) or "careers" in h_norm:
                official_pages.setdefault("careers", full_url)

            # Contact / Support
            if any(k in t_norm for k in ["contact", "support"]) or "contact" in h_norm:
                official_pages.setdefault("contact", full_url)
                contact_page = full_url

            # Investors / IR
            if any(k in t_norm for k in ["investor", "investors", "ir"]) or "investor" in h_norm:
                official_pages.setdefault("investors", full_url)

            # Product / Service / Solution buckets
            if any(k in t_norm for k in ["products", "product"]):
                products.append({
                    "name": text or "Product listing",
                    "category": "product_nav_link"
                })
            if any(k in t_norm for k in ["services", "service"]):
                services.append(text or "Service listing")
            if any(k in t_norm for k in ["solutions", "solution"]):
                solutions_list.append(text or "Solution listing")

            # Social profiles by domain
            parsed = urlparse(full_url)
            host = parsed.netloc.lower()
            if "linkedin.com" in host and "linkedin" not in social_profiles:
                social_profiles["linkedin"] = full_url
            elif any(s in host for s in ["twitter.com", "x.com"]) and "twitter" not in social_profiles:
                social_profiles["twitter"] = full_url
            elif "facebook.com" in host and "facebook" not in social_profiles:
                social_profiles["facebook"] = full_url
            elif "youtube.com" in host and "youtube" not in social_profiles:
                social_profiles["youtube"] = full_url
            elif "instagram.com" in host and "instagram" not in social_profiles:
                social_profiles["instagram"] = full_url

        solutions_dict = None
        if solutions_list:
            solutions_dict = {"enterprise": solutions_list}

        return {
            "official_pages": official_pages,
            "products": products,
            "services": services,
            "solutions": solutions_dict,
            "social_profiles": social_profiles or None,
            "contact": contact_page,
        }

    # ── Main fetch ──────────────────────────────────────────────────────────

    async def fetch(self, target: Any) -> List[ResearchEvidence]:
        company = self._extract_identifier(target)
        if not company:
            return []
        company_clean = company.strip()
        ticker_hint = getattr(target, "ticker", None) if hasattr(target, "ticker") else None
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        async with httpx.AsyncClient(
            headers=_BROWSER_HEADERS,
            follow_redirects=True,
            timeout=14.0,
        ) as client:
            # Layer 1: parallel identity fetch
            wiki_task = self._fetch_wikipedia(client, company_clean)
            yf_task = self._fetch_yfinance(ticker_hint, company_clean)

            wiki_data, yf_data = await asyncio.gather(wiki_task, yf_task)

            # Layer 2: parallel supplement fetch
            website_for_sw = (
                yf_data.get("website")
                or wiki_data.get("website")
                or f"{company_clean.lower().replace(' ','')}.com"
            )
            cb_task = self._fetch_crunchbase(client, company_clean)
            sw_task = self._fetch_similarweb(client, website_for_sw)
            li_task = self._fetch_linkedin(client, company_clean)
            
            website_candidate = (
                yf_data.get("website")
                or wiki_data.get("website")
                or website_for_sw
            )
            crawl_task = self._crawl_official_site(client, website_candidate)

            cb_data, sw_data, li_data, crawl_data = await asyncio.gather(cb_task, sw_task, li_task, crawl_task)

        # ── Merge: prefer high-authority over low-authority ────────────────
        def first_non_empty(*vals):
            for v in vals:
                if v:
                    return v
            return None

        resolved_name = first_non_empty(
            wiki_data.get("name"), yf_data.get("long_name"), company_clean
        )
        overview = first_non_empty(
            wiki_data.get("overview"),
            yf_data.get("overview"),
            li_data.get("description"),
            cb_data.get("description"),
        ) or ""
        headquarters = first_non_empty(
            wiki_data.get("headquarters"), yf_data.get("headquarters")
        )
        website = first_non_empty(
            wiki_data.get("website"), yf_data.get("website"), website_for_sw
        )
        founders = wiki_data.get("founders") or []
        employee_count = first_non_empty(
            wiki_data.get("employee_count"), yf_data.get("employee_count")
        )

        # Merge leadership (Wikipedia key_people + yfinance officers)
        leadership: List[Dict[str, str]] = list(wiki_data.get("leadership") or [])
        seen_names = {l["name"] for l in leadership}
        for officer in yf_data.get("officers") or []:
            if officer.get("name") and officer["name"] not in seen_names:
                leadership.append(officer)
                seen_names.add(officer["name"])

        # Competitors from yfinance industry
        industry = yf_data.get("industry", "")
        sector = yf_data.get("sector", "")
        competitors = self._get_competitors(industry, sector)

        # Funding from Crunchbase
        funding_total = cb_data.get("funding_total", "N/A")
        last_round = cb_data.get("last_round", "N/A")
        founded_year = cb_data.get("founded_year")

        # Web presence
        monthly_visits = sw_data.get("monthly_visits")
        global_rank = sw_data.get("global_rank")

        # ── Emit ResearchEvidence per fact ────────────────────────────────
        evidence_list: List[ResearchEvidence] = []

        def emit(attr: str, val: Any, source: str, source_type: str, confidence: float):
            if val is None or val == "" or val == [] or val == "N/A":
                return
            evidence_list.append(
                ResearchEvidence(
                    id=CitationManager.generate_id(source, company_clean, attr, now_str),
                    entity=company_clean,
                    attribute=attr,
                    value=val,
                    source=source,
                    source_type=source_type,
                    confidence=confidence,
                    freshness=now_str,
                )
            )

        # Identity (highest confidence — from multiple authoritative sources)
        emit("name", resolved_name, "company_profile", "mcp", 0.95)
        emit("overview", overview[:1000], "company_profile", "mcp", 0.88)
        emit("headquarters", headquarters, "company_profile", "mcp", 0.88)
        emit("website", website, "company_profile", "mcp", 0.88)
        emit("founders", founders, "company_profile", "mcp", 0.85)
        emit("employee_count", employee_count, "company_profile", "mcp", 0.82)
        emit("leadership", leadership, "company_profile", "mcp", 0.80)
        emit("competitors", competitors, "company_profile", "mcp", 0.75)

        # Financial identity
        emit("industry", industry, "yfinance", "mcp", 0.85)
        emit("sector", sector, "yfinance", "mcp", 0.85)
        emit("ticker", yf_data.get("ticker"), "yfinance", "mcp", 0.95)

        # Crunchbase enrichment
        emit("funding_total", funding_total, "crunchbase", "mcp", 0.78)
        emit("last_round", last_round, "crunchbase", "mcp", 0.78)
        emit("founded_year", founded_year, "crunchbase", "mcp", 0.80)

        # Web presence signals
        emit("monthly_visits", monthly_visits, "similarweb", "mcp", 0.70)
        emit("global_web_rank", global_rank, "similarweb", "mcp", 0.70)
        
        # Official web footprint (from crawler)
        emit("official_pages", crawl_data.get("official_pages"), "web_crawler", "mcp", 0.80)
        emit("products", crawl_data.get("products"), "web_crawler", "mcp", 0.70)
        emit("services", crawl_data.get("services"), "web_crawler", "mcp", 0.70)
        emit("solutions", crawl_data.get("solutions"), "web_crawler", "mcp", 0.70)
        emit("social_profiles", crawl_data.get("social_profiles"), "web_crawler", "mcp", 0.80)
        emit("contact", crawl_data.get("contact"), "web_crawler", "mcp", 0.75)
        
        from services.research.providers.shared_utils import _write_json
        _write_json(
            f"company_evidence_{company_clean.replace(' ', '_')[:40]}.json",
            [e.model_dump(mode='json') for e in evidence_list]
        )

        logger.info(
            f"CompanyProvider: {len(evidence_list)} evidence items for '{company_clean}'"
            f" (wiki={bool(wiki_data)}, yf={bool(yf_data)}, cb={bool(cb_data)}, sw={bool(sw_data)})"
        )
        return evidence_list
