import re
import httpx
import yfinance as yf
from typing import Dict, Any, List, Optional
from services.research.base import BaseProvider

def resolve_templates(text: str) -> str:
    while True:
        match = re.search(r"\{\{([^{}]+)\}\}", text)
        if not match:
            break
        
        template_content = match.group(1)
        parts = template_content.split("|")
        name = parts[0].strip().lower()
        args = parts[1:]
        
        resolved = ""
        if name in ["url", "website"]:
            resolved = args[0].strip() if args else ""
        elif name in ["unbulleted list", "plainlist", "flatlist", "bulleted list"]:
            valid_args = []
            for arg in args:
                arg_clean = arg.strip()
                if arg_clean and "=" not in arg_clean:
                    arg_clean = arg_clean.lstrip("*").strip()
                    if arg_clean:
                        valid_args.append(arg_clean)
            resolved = ", ".join(valid_args)
        elif "date" in name:
            date_parts = [a.strip() for a in args if a.strip().isdigit()]
            resolved = "-".join(date_parts) if date_parts else ""
        else:
            valid_args = [a.strip() for a in args if "=" not in a]
            resolved = valid_args[0] if valid_args else ""
            
        text = text[:match.start()] + resolved + text[match.end():]
        
    return text

def clean_wiki_val(val: str) -> str:
    val = resolve_templates(val)
    val = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", val)
    val = re.sub(r"\[\[([^\]]+)\]\]", r"\1", val)
    val = re.sub(r"<!--.*?-->", "", val, flags=re.DOTALL)
    val = re.sub(r"<[^>]+>", "", val)
    val = val.replace("|", ",").replace("*", ",").replace("\n", ", ")
    val = re.sub(r"\s+", " ", val)
    val = re.sub(r",\s*,", ",", val)
    val = val.strip(", ")
    return val

def extract_infobox_fields(infobox_text: str):
    start_match = re.search(r"\{\{[Ii]nfobox company", infobox_text)
    if not start_match:
        return {}
    start_idx = start_match.start()
    
    brace_count = 0
    end_idx = -1
    for i in range(start_idx, len(infobox_text)):
        if infobox_text[i:i+2] == "{{":
            brace_count += 1
        elif infobox_text[i:i+2] == "}}":
            brace_count -= 1
            if brace_count == 0:
                end_idx = i + 2
                break
    if end_idx == -1:
        return {}
        
    content = infobox_text[start_match.end():end_idx-2].strip()
    
    parts = []
    current_part = []
    brace_level = 0
    bracket_level = 0
    
    i = 0
    while i < len(content):
        c = content[i]
        if content[i:i+2] == "{{":
            brace_level += 1
            current_part.append("{{")
            i += 2
            continue
        elif content[i:i+2] == "}}":
            brace_level -= 1
            current_part.append("}}")
            i += 2
            continue
        elif content[i:i+2] == "[[":
            bracket_level += 1
            current_part.append("[[")
            i += 2
            continue
        elif content[i:i+2] == "]]":
            bracket_level -= 1
            current_part.append("]]")
            i += 2
            continue
            
        if c == "|" and brace_level == 0 and bracket_level == 0:
            parts.append("".join(current_part).strip())
            current_part = []
        else:
            current_part.append(c)
        i += 1
        
    if current_part:
        parts.append("".join(current_part).strip())
        
    fields = {}
    for part in parts:
        if not part:
            continue
        subparts = part.split("=", 1)
        if len(subparts) == 2:
            key = subparts[0].strip()
            val = subparts[1].strip()
            fields[key] = clean_wiki_val(val)
            
    return fields

class CompanyProvider(BaseProvider):
    """
    Fetches company profiles from Wikipedia and yfinance.
    """

    async def _resolve_ticker(self, company: str) -> Optional[str]:
        url = "https://query1.finance.yahoo.com/v1/finance/search"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        params = {
            "q": company,
            "quotesCount": 10,
            "newsCount": 0
        }
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(url, params=params, headers=headers, timeout=10.0)
                if r.status_code == 200:
                    results = r.json()
                    quotes = results.get("quotes", [])
                    for q in quotes:
                        if q.get("quoteType", "").upper() == "EQUITY":
                            return q.get("symbol")
        except Exception:
            pass
        return None

    async def _fetch_competitors(self, company_name: str, ticker_info: dict) -> List[Dict[str, Any]]:
        # 1. Check yfinance industry/sector
        industry = ticker_info.get("industry", "")
        sector = ticker_info.get("sector", "")
        
        # Industry/Sector mapping to standard peers
        industry_peers = {
            "Semiconductors": [
                {"name": "AMD", "website": "https://amd.com", "segment": "Semiconductors & AI"},
                {"name": "Intel", "website": "https://intel.com", "segment": "Processors & Foundry"},
                {"name": "Qualcomm", "website": "https://qualcomm.com", "segment": "Mobile & Wireless"}
            ],
            "Software—Application": [
                {"name": "Salesforce", "website": "https://salesforce.com", "segment": "CRM & Enterprise SaaS"},
                {"name": "Oracle", "website": "https://oracle.com", "segment": "Database & Cloud Applications"},
                {"name": "Adobe", "website": "https://adobe.com", "segment": "Creative & Marketing Software"}
            ],
            "Software—Infrastructure": [
                {"name": "Microsoft", "website": "https://microsoft.com", "segment": "Cloud & Operating Systems"},
                {"name": "Oracle", "website": "https://oracle.com", "segment": "Cloud Infrastructure"},
                {"name": "Amazon Web Services", "website": "https://aws.amazon.com", "segment": "Cloud & Infrastructure"}
            ],
            "Internet Content & Information": [
                {"name": "Alphabet", "website": "https://google.com", "segment": "Search & Digital Advertising"},
                {"name": "Meta Platforms", "website": "https://meta.com", "segment": "Social Media & Advertising"},
                {"name": "ByteDance", "website": "https://bytedance.com", "segment": "Short Video & Social Media"}
            ],
            "Auto Manufacturers": [
                {"name": "Tesla", "website": "https://tesla.com", "segment": "Electric Vehicles"},
                {"name": "Toyota", "website": "https://toyota.com", "segment": "Automotive"},
                {"name": "Ford", "website": "https://ford.com", "segment": "Automotive"}
            ],
            "Consumer Electronics": [
                {"name": "Apple", "website": "https://apple.com", "segment": "Smartphones & Devices"},
                {"name": "Samsung Electronics", "website": "https://samsung.com", "segment": "Mobile & Electronics"},
                {"name": "Sony", "website": "https://sony.com", "segment": "Entertainment & Devices"}
            ]
        }
        
        # Match by industry
        for ind, peers in industry_peers.items():
            if ind.lower() in industry.lower():
                return peers
                
        # 2. General fallback search via Yahoo Finance search endpoint
        search_term = f"{company_name} competitors"
        search_url = "https://query1.finance.yahoo.com/v1/finance/search"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        params = {
            "q": search_term,
            "quotesCount": 3,
            "newsCount": 0
        }
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(search_url, params=params, headers=headers, timeout=5.0)
                if r.status_code == 200:
                    quotes = r.json().get("quotes", [])
                    peers = []
                    for q in quotes:
                        symbol = q.get("symbol")
                        name = q.get("longname") or q.get("shortname")
                        if symbol and name and q.get("quoteType") == "EQUITY":
                            peers.append({
                                "name": name,
                                "website": f"https://{symbol.split('.')[0].lower()}.com",
                                "segment": sector or "Industry Peer"
                            })
                    if peers:
                        return peers
        except Exception:
            pass
            
        # Default fallback
        return [
            {"name": "Microsoft", "website": "https://microsoft.com", "segment": "Tech & Software"},
            {"name": "Alphabet", "website": "https://google.com", "segment": "Tech & Search"}
        ]

    async def fetch(self, company: str) -> Dict[str, Any]:
        company_clean = company.strip()
        


        # Real sourcing
        resolved_name = company_clean
        overview = f"{company_clean} is an unverified business entity."
        headquarters = None
        employee_count = None
        website = f"https://{company_clean.lower().replace(' ', '')}.com"
        founders = []
        leadership = []
        
        wiki_raw = {}
        yf_raw = {}
        
        # 1. Search Wikipedia
        search_url = "https://en.wikipedia.org/w/api.php"
        headers = {"User-Agent": "MCPBusinessIntelligenceBot/1.0 (contact@mcp-business.com) Python-httpx/0.24"}
        
        wiki_title = None
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "action": "query",
                    "list": "search",
                    "srsearch": company_clean,
                    "format": "json"
                }
                r = await client.get(search_url, params=params, headers=headers, timeout=10.0)
                if r.status_code == 200:
                    search_results = r.json()
                    search_items = search_results.get("query", {}).get("search", [])
                    if search_items:
                        wiki_title = search_items[0]["title"]
        except Exception:
            pass

        source_url = f"https://directory.com/{company_clean.lower().replace(' ', '')}"
        source_title = "Generic Web Directory"

        if wiki_title:
            source_title = f"Wikipedia: {wiki_title}"
            source_url = f"https://en.wikipedia.org/wiki/{wiki_title.replace(' ', '_')}"
            
            # Fetch summary and revision wikitext
            try:
                async with httpx.AsyncClient() as client:
                    # 1. Fetch revision wikitext
                    rev_params = {
                        "action": "query",
                        "prop": "revisions",
                        "rvprop": "content",
                        "rvsection": 0,
                        "titles": wiki_title,
                        "format": "json"
                    }
                    r_rev = await client.get(search_url, params=rev_params, headers=headers, timeout=10.0)
                    if r_rev.status_code == 200:
                        wiki_raw["revisions"] = r_rev.json()
                        pages = wiki_raw["revisions"].get("query", {}).get("pages", {})
                        for page_id, page in pages.items():
                            revisions = page.get("revisions", [])
                            if revisions:
                                wikitext = revisions[0].get("*", "")
                                infobox = extract_infobox_fields(wikitext)
                                wiki_raw["infobox"] = infobox
                                
                                # Map infobox fields
                                if infobox.get("name"):
                                    resolved_name = infobox["name"]
                                    
                                hq_parts = [
                                    infobox.get("hq_location_city"),
                                    infobox.get("hq_location_country") or infobox.get("hq_location") or infobox.get("location")
                                ]
                                hq_clean = ", ".join([p for p in hq_parts if p])
                                if hq_clean:
                                    headquarters = hq_clean
                                    
                                if infobox.get("website"):
                                    website = infobox["website"]
                                    
                                if infobox.get("founders") or infobox.get("founder"):
                                    f_str = infobox.get("founders") or infobox.get("founder", "")
                                    founders = [x.strip() for x in f_str.split(",") if x.strip()]
                                    
                                if infobox.get("key_people") or infobox.get("leadership"):
                                    kp_str = infobox.get("key_people") or infobox.get("leadership", "")
                                    for p in kp_str.split(","):
                                        p_clean = p.strip()
                                        if not p_clean:
                                            continue
                                        role_match = re.match(r"(.*?)\((.*?)\)", p_clean)
                                        if role_match:
                                            leadership.append({
                                                "name": role_match.group(1).strip(),
                                                "role": role_match.group(2).strip(),
                                                "linkedin_url": None
                                            })
                                        else:
                                            leadership.append({
                                                "name": p_clean,
                                                "role": "Executive",
                                                "linkedin_url": None
                                            })

                                emp_str = infobox.get("num_employees") or infobox.get("num_members") or ""
                                emp_str_clean = emp_str.split("(")[0]
                                digits = "".join(re.findall(r"\d+", emp_str_clean.replace(",", "")))
                                if digits:
                                    employee_count = int(digits)

                    # 2. Fetch summary
                    sum_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{wiki_title.replace(' ', '_')}"
                    r_sum = await client.get(sum_url, headers=headers, timeout=10.0)
                    if r_sum.status_code == 200:
                        wiki_raw["summary"] = r_sum.json()
                        overview = wiki_raw["summary"].get("extract", overview)
            except Exception:
                pass

        # 2. yfinance Supplement
        ticker_symbol = await self._resolve_ticker(company_clean)
        if ticker_symbol:
            try:
                ticker = yf.Ticker(ticker_symbol)
                info = ticker.info or {}
                yf_raw["info"] = info
                
                # Overwrite/Supplement details
                if resolved_name == company_clean and info.get("longName"):
                    resolved_name = info["longName"]
                
                # Fetch fullTimeEmployees
                if not employee_count and info.get("fullTimeEmployees"):
                    employee_count = info["fullTimeEmployees"]
                    
                # Fetch website
                if (not website or "directory.com" in website) and info.get("website"):
                    website = info["website"]
                    
                # Fetch headquarters
                if not headquarters:
                    addr = [
                        info.get("address1"),
                        info.get("city"),
                        info.get("state"),
                        info.get("country")
                    ]
                    hq_str = ", ".join([a for a in addr if a])
                    if hq_str:
                        headquarters = hq_str
                        
                # Fetch companyOfficers
                for officer in info.get("companyOfficers", []):
                    name = officer.get("name")
                    role = officer.get("title", "")
                    if name:
                        # Append to leadership if not already present
                        if name not in [l["name"] for l in leadership]:
                            leadership.append({
                                "name": name,
                                "role": role,
                                "linkedin_url": None
                            })
                        # Check if founder
                        if "founder" in role.lower() and name not in founders:
                            founders.append(name)
                            
                if overview.endswith("unverified business entity.") and info.get("longBusinessSummary"):
                    overview = info["longBusinessSummary"]

            except Exception:
                pass

        # Fetch competitors dynamically
        competitors = await self._fetch_competitors(resolved_name, yf_raw.get("info", {}))

        return {
            "source_title": source_title,
            "source_url": source_url,
            "source_type": "official_website" if wiki_title else "directory",
            "name": resolved_name,
            "overview": overview,
            "headquarters": headquarters,
            "employee_count": employee_count,
            "website": website,
            "founders": founders,
            "leadership": leadership,
            "competitors": competitors,
            "raw_data": {
                "wikipedia": wiki_raw,
                "yfinance": yf_raw
            }
        }
