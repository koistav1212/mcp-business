import asyncio
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx
import yfinance as yf

from services.research.base import BaseProvider
from services.knowledge.evidence import ResearchEvidence
from services.research.providers.shared_utils import _get, _write_json, _emit, logger, BROWSER_HEADERS, JSON_HEADERS

class PeopleProvider(BaseProvider):
    """
    Leadership and talent intelligence.
    """
    async def fetch(self, target: Any) -> List[ResearchEvidence]:
        company = self._extract_identifier(target, preferred_key="company")
        if not company:
            return []
        company_clean = company.strip()
        ticker = getattr(target, "ticker", None) if hasattr(target, "ticker") else None
        website = getattr(target, "website", None) if hasattr(target, "website") else None
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        evidence_list: List[ResearchEvidence] = []

        async with httpx.AsyncClient(headers=BROWSER_HEADERS, follow_redirects=True, timeout=12.0) as client:
            tasks = [
                self._fetch_yfinance_officers(ticker),
                self._fetch_linkedin(client, company_clean),
                self._fetch_github_org(client, company_clean),
                self._fetch_glassdoor(client, company_clean),
                self._fetch_indeed_jobs(client, company_clean),
                self._fetch_news_leadership(client, company_clean),
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        yf_people, li_people, gh_data, gd_data, indeed_data, news_leaders = (
            r if isinstance(r, (dict, list)) else ({} if i < 5 else [])
            for i, r in enumerate(results)
        )

        leadership: List[Dict] = []
        seen_names: set = set()

        for person in (yf_people.get("officers") or []):
            if person.get("name") and person["name"] not in seen_names:
                leadership.append({
                    "name": person["name"],
                    "role": person.get("title", "Executive"),
                    "source": "yfinance",
                    "total_pay": person.get("totalPay"),
                })
                seen_names.add(person["name"])

        for person in (li_people.get("executives") or []):
            if person.get("name") and person["name"] not in seen_names:
                leadership.append({
                    "name": person["name"],
                    "role": person.get("role", "Executive"),
                    "source": "linkedin",
                })
                seen_names.add(person["name"])

        for person in (news_leaders or []):
            if person.get("name") and person["name"] not in seen_names:
                leadership.append({
                    "name": person["name"],
                    "role": person.get("role", "Executive"),
                    "source": "news",
                })
                seen_names.add(person["name"])

        _emit(evidence_list, entity=company_clean, attribute="leadership",
              value=leadership[:10], source="people_pipeline", source_type="mcp",
              confidence=0.85, now_str=now_str)

        if indeed_data:
            _emit(evidence_list, entity=company_clean, attribute="hiring_signals",
                  value=indeed_data, source="indeed", source_type="mcp",
                  confidence=0.75, now_str=now_str)
            _emit(evidence_list, entity=company_clean, attribute="open_roles_by_dept",
                  value=indeed_data.get("by_department", {}), source="indeed",
                  source_type="mcp", confidence=0.70, now_str=now_str)

        if gh_data:
            _emit(evidence_list, entity=company_clean, attribute="github_repo_count",
                  value=gh_data.get("public_repos"), source="github", source_type="mcp",
                  confidence=0.90, now_str=now_str)
            _emit(evidence_list, entity=company_clean, attribute="github_contributors",
                  value=gh_data.get("top_contributors"), source="github", source_type="mcp",
                  confidence=0.85, now_str=now_str)
            _emit(evidence_list, entity=company_clean, attribute="github_languages",
                  value=gh_data.get("top_languages"), source="github", source_type="mcp",
                  confidence=0.80, now_str=now_str)

        if gd_data:
            _emit(evidence_list, entity=company_clean, attribute="glassdoor_rating",
                  value=gd_data.get("overall_rating"), source="glassdoor", source_type="mcp",
                  confidence=0.70, now_str=now_str)
            _emit(evidence_list, entity=company_clean, attribute="glassdoor_ceo_approval",
                  value=gd_data.get("ceo_approval"), source="glassdoor", source_type="mcp",
                  confidence=0.70, now_str=now_str)
            _emit(evidence_list, entity=company_clean, attribute="glassdoor_recommend_pct",
                  value=gd_data.get("recommend_to_friend_pct"), source="glassdoor",
                  source_type="mcp", confidence=0.70, now_str=now_str)

        _write_json(f"people_{company_clean.replace(' ', '_')[:20]}.json",
                    [e.model_dump(mode='json') for e in evidence_list])
        logger.info(f"PeopleProvider: {len(evidence_list)} evidence items for '{company_clean}'")
        return evidence_list

    async def _fetch_yfinance_officers(self, ticker: Optional[str]) -> Dict:
        if not ticker or "MOCK" in ticker.upper() or "PRIVATE" in ticker.upper():
            return {}
        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None, lambda: yf.Ticker(ticker.upper()).info or {}
            )
            return {"officers": info.get("companyOfficers", [])}
        except Exception:
            return {}

    async def _fetch_linkedin(self, client: httpx.AsyncClient, company: str) -> Dict:
        slug = company.lower().replace(" ", "-").replace(",", "").replace(".", "")
        url = f"https://www.linkedin.com/company/{slug}/"
        r = await _get(client, url)
        if not r:
            return {}
        html = r.text
        out: Dict = {"executives": []}

        ld_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
        if ld_match:
            try:
                ld = json.loads(ld_match.group(1))
                if isinstance(ld, list):
                    ld = ld[0]
                emp = ld.get("numberOfEmployees", {})
                if emp:
                    out["employee_range"] = f"{emp.get('minValue', '?')}-{emp.get('maxValue', '?')}"
            except Exception:
                pass

        exec_pattern = re.compile(
            r'(?:CEO|CFO|CTO|COO|President|VP|Director|Chief)\s+(?:of\s+)?([A-Z][a-z]+ [A-Z][a-z]+)',
            re.IGNORECASE,
        )
        for m in exec_pattern.finditer(html[:10000]):
            name = m.group(1)
            role = m.group(0).split(name)[0].strip()
            if name not in [e["name"] for e in out["executives"]]:
                out["executives"].append({"name": name, "role": role})
                if len(out["executives"]) >= 6:
                    break
        return out

    async def _fetch_github_org(self, client: httpx.AsyncClient, company: str) -> Dict:
        slug = company.lower().replace(" ", "").replace(",", "").replace(".", "")
        url = f"https://api.github.com/orgs/{slug}"
        r = await _get(client, url, headers={**JSON_HEADERS, "Accept": "application/vnd.github.v3+json"})
        if not r:
            return {}
        try:
            org = r.json()
            repos_r = await _get(
                client,
                f"https://api.github.com/orgs/{slug}/repos?sort=stars&per_page=10",
                headers={**JSON_HEADERS, "Accept": "application/vnd.github.v3+json"},
            )
            languages: Dict[str, int] = {}
            if repos_r:
                for repo in repos_r.json():
                    lang = repo.get("language")
                    if lang:
                        languages[lang] = languages.get(lang, 0) + 1
            return {
                "public_repos": org.get("public_repos"),
                "followers": org.get("followers"),
                "top_languages": sorted(languages, key=lambda k: -languages[k])[:5],
                "blog": org.get("blog"),
                "github_url": org.get("html_url"),
            }
        except Exception:
            return {}

    async def _fetch_glassdoor(self, client: httpx.AsyncClient, company: str) -> Dict:
        search_url = f"https://www.glassdoor.com/Search/results.htm?keyword={quote_plus(company)}"
        r = await _get(client, search_url)
        if not r:
            return {}
        html = r.text
        out: Dict = {}
        rating_m = re.search(r'"overallRating":\s*"?([0-9.]+)"?', html)
        if rating_m:
            out["overall_rating"] = float(rating_m.group(1))
        ceo_m = re.search(r'"ceoApproval":\s*"?([0-9.]+)"?', html) or re.search(
            r'CEO Approval.*?([\d]+)%', html
        )
        if ceo_m:
            out["ceo_approval"] = float(ceo_m.group(1))
        rec_m = re.search(r'"recommendToFriend":\s*"?([0-9.]+)"?', html)
        if rec_m:
            out["recommend_to_friend_pct"] = float(rec_m.group(1))
        return out

    async def _fetch_indeed_jobs(self, client: httpx.AsyncClient, company: str) -> Optional[Dict]:
        url = f"https://www.indeed.com/jobs?q=&l=&sc=0kf%3Acmf({quote_plus(company)})%3B&sort=date"
        r = await _get(client, url)
        if not r:
            return None
        html = r.text
        count_m = re.search(r'([\d,]+)\s+(?:jobs?|positions?)\s+at\s+' + re.escape(company), html, re.I)
        if not count_m:
            count_m = re.search(r'"totalResults":\s*(\d+)', html)
        total = int(count_m.group(1).replace(",", "")) if count_m else 0

        dept_kw = {
            "Engineering": ["engineer", "developer", "software", "backend", "frontend", "devops", "sre"],
            "AI/ML": ["machine learning", "ai", "ml", "data scientist", "nlp", "llm"],
            "Sales": ["sales", "account executive", "business development", "revenue"],
            "Marketing": ["marketing", "brand", "content", "growth", "demand gen"],
            "Finance": ["finance", "accounting", "analyst", "controller", "fp&a"],
            "HR": ["recruiting", "hr", "people", "talent", "human resources"],
            "Product": ["product manager", "product owner", "ux", "ui designer"],
        }
        by_dept: Dict[str, int] = {}
        for dept, kws in dept_kw.items():
            dept_count_m = re.search(
                r'(' + "|".join(kws) + r').*?(\d+)\s+(?:open)?\s*(?:roles?|jobs?|positions?)',
                html, re.IGNORECASE,
            )
            if dept_count_m:
                by_dept[dept] = int(dept_count_m.group(2))

        job_titles = re.findall(r'"jobTitle":\s*"([^"]{5,80})"', html)[:15]
        return {
            "total_open_roles": total,
            "by_department": by_dept,
            "sample_titles": list(set(job_titles)),
            "source_url": url,
        }

    async def _fetch_news_leadership(
        self, client: httpx.AsyncClient, company: str
    ) -> List[Dict]:
        query = quote_plus(f"{company} CEO CFO CTO appoints hires resigns")
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
        r = await _get(client, url)
        if not r:
            return []
        people = []
        try:
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:10]:
                title_el = item.find("title")
                title = title_el.text if title_el is not None else ""
                m = re.search(
                    r"([A-Z][a-z]+ [A-Z][a-z]+) (?:appointed|named|hired|joins|becomes)(?: as| new)? ([A-Z][^,\.]{3,40})",
                    title or "",
                )
                if m:
                    people.append({"name": m.group(1), "role": m.group(2).strip()})
        except Exception:
            pass
        return people
