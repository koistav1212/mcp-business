import os
import json
import httpx
import re
from typing import List, Dict, Any, Optional
from services.research.models import EntityResolution

class EntityResolver:
    """
    Resolves free-text company queries to structured EntityResolution objects
    containing official name, ticker, CIK, exchange, website, and confidence.
    """
    def __init__(self):
        self.tickers_cache_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "storage", "company_tickers.json"
        )
        self.sec_tickers = {}
        self.sec_first_word_index = {}
        # Try loading from local cache first
        self._load_cache()

    def _build_indexes(self):
        self.sec_first_word_index = {}
        for k, v in self.sec_tickers.items():
            title = v.get("title", "")
            ticker = v.get("ticker", "").upper()
            if title and ticker:
                title_clean = title.lower()
                words = title_clean.split()
                if words:
                    first_word = words[0]
                    if first_word not in self.sec_first_word_index:
                        self.sec_first_word_index[first_word] = []
                    self.sec_first_word_index[first_word].append({
                        "name": title,
                        "ticker": ticker
                    })

    def _load_cache(self):
        if os.path.exists(self.tickers_cache_path):
            try:
                with open(self.tickers_cache_path, "r", encoding="utf-8") as f:
                    self.sec_tickers = json.load(f)
                self._build_indexes()
            except Exception:
                pass

    async def _fetch_sec_tickers(self) -> dict:
        url = "https://www.sec.gov/files/company_tickers.json"
        headers = {
            "User-Agent": "MCPBusinessIntelligenceBot/1.0 (contact@mcp-business.com)"
        }
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(url, headers=headers, timeout=10.0)
                if r.status_code == 200:
                    data = r.json()
                    # Ensure storage dir exists
                    os.makedirs(os.path.dirname(self.tickers_cache_path), exist_ok=True)
                    with open(self.tickers_cache_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    self.sec_tickers = data
                    self._build_indexes()
                    return data
        except Exception:
            pass
        return self.sec_tickers

    async def get_candidates(self, query: str) -> List[EntityResolution]:
        # Ensure we have the SEC tickers database loaded
        if not self.sec_tickers:
            await self._fetch_sec_tickers()

        # Clean query
        query_clean = query.strip()
        query_lower = query_clean.lower()

        # Prefer an authoritative exact SEC match before noisy remote search.
        normalized_query = self._normalize_company_name(query_clean)
        local_exact = []
        for value in self.sec_tickers.values():
            title = value.get("title", "")
            ticker = value.get("ticker", "").upper()
            if not title or not ticker:
                continue
            normalized_title = self._normalize_company_name(title)
            if normalized_query in {normalized_title, ticker.lower()}:
                display_name = self._display_company_name(title)
                local_exact.append(EntityResolution(
                    company_name=display_name,
                    ticker=ticker,
                    cik=str(value.get("cik_str", "")).zfill(10) or None,
                    exchange=None,
                    website=f"{normalized_title.replace(' ', '')}.com",
                    confidence=0.99,
                ))
        # 1. Private company check removed. Will fallback to Wikipedia search if no candidates found on Yahoo.

        # Find matching candidates using Yahoo Finance search
        search_url = "https://query1.finance.yahoo.com/v1/finance/search"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        params = {
            "q": query_clean,
            "quotesCount": 10,
            "newsCount": 0
        }
        
        quotes = []
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(search_url, params=params, headers=headers, timeout=10.0)
                if r.status_code == 200:
                    quotes = r.json().get("quotes", [])
        except Exception:
            pass

        candidates = []
        sec_by_ticker = {}
        sec_by_name = {}
        for k, v in self.sec_tickers.items():
            t = v.get("ticker", "").upper()
            c = str(v.get("cik_str", ""))
            n = v.get("title", "").upper()
            if t:
                sec_by_ticker[t] = {"cik": c, "title": v.get("title")}
            if n:
                sec_by_name[n] = {"cik": c, "ticker": t}

        for q in quotes:
            symbol = q.get("symbol", "").upper()
            quote_type = q.get("quoteType", "").upper()
            exchange = q.get("exchDisp", "").upper() or q.get("exchange", "").upper()
            long_name = q.get("longname", q.get("shortname", ""))
            sector = q.get("sector")
            
            if quote_type != "EQUITY":
                continue
                
            base_symbol = symbol.split(".")[0]
            sec_match = sec_by_ticker.get(base_symbol) or sec_by_ticker.get(symbol)
            
            cik = None
            resolved_name = long_name
            if sec_match:
                cik = sec_match["cik"].zfill(10)
                resolved_name = sec_match["title"]
            else:
                name_upper = long_name.upper()
                if name_upper in sec_by_name:
                    cik = sec_by_name[name_upper]["cik"].zfill(10)
                    
            confidence = 0.5
            name_words = set(resolved_name.lower().replace(",", "").replace(".", "").split())
            query_words = set(query_lower.split())
            intersection = name_words.intersection(query_words)
            
            if intersection:
                confidence += 0.2
            if query_lower in resolved_name.lower():
                confidence += 0.1
            if symbol.split(".")[0].lower() in query_lower:
                confidence += 0.1
            if sector is not None:
                confidence += 0.2
            if cik is not None:
                confidence += 0.2
                
            # Penalize ETFs or Funds indexed under EQUITY
            lower_name = resolved_name.lower()
            if any(term in lower_name for term in ["etf", "etp", "index", "fund", "tracker", "shares 3x", "daily target"]):
                confidence -= 0.5
                
            confidence = max(0.01, min(round(confidence, 2), 0.99))
            
            website_guess = f"{resolved_name.lower().split()[0].replace(',', '').replace('.', '')}.com"
            if base_symbol.isalpha():
                website_guess = f"{base_symbol.lower()}.com"

            candidates.append(EntityResolution(
                company_name=resolved_name,
                ticker=symbol,
                cik=cik,
                exchange=exchange,
                website=website_guess,
                confidence=confidence
            ))

        if not candidates and local_exact:
            candidates.extend(local_exact)
            
        if not candidates:
            # Fallback to Wikipedia search for unlisted/private companies
            wiki_url = "https://en.wikipedia.org/w/api.php"
            wiki_params = {
                "action": "query",
                "list": "search",
                "srsearch": query_clean,
                "format": "json"
            }
            wiki_headers = {
                "User-Agent": "MCPBusinessIntelligenceBot/1.0 (contact@mcp-business.com)"
            }
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.get(wiki_url, params=wiki_params, headers=wiki_headers, timeout=10.0)
                    if r.status_code == 200:
                        search_results = r.json().get("query", {}).get("search", [])
                        if search_results:
                            top_result = search_results[0]
                            title = top_result.get("title")
                            if title:
                                # Estimate website guess from title
                                first_word = title.lower().split()[0].replace(",", "").replace(".", "")
                                website_guess = f"{first_word}.com"
                                candidates.append(EntityResolution(
                                    company_name=title,
                                    ticker=None,
                                    cik=None,
                                    exchange="PRIVATE",
                                    website=website_guess,
                                    confidence=0.85
                                ))
            except Exception:
                pass

        candidates.sort(key=lambda x: x.confidence, reverse=True)
        
        if not candidates:
            candidates.append(EntityResolution(
                company_name=query.capitalize(),
                ticker=None,
                cik=None,
                exchange="UNKNOWN",
                website=f"{query_lower.replace(' ', '')}.com",
                confidence=0.1
            ))
            
        return candidates

    @staticmethod
    def _normalize_company_name(value: str) -> str:
        cleaned = re.sub(r"[^a-z0-9\s]", " ", value.lower())
        words = cleaned.split()
        suffixes = {"inc", "incorporated", "corp", "corporation", "co", "company", "ltd", "limited", "plc"}
        while words and words[-1] in suffixes:
            words.pop()
        return " ".join(words)

    @staticmethod
    def _display_company_name(value: str) -> str:
        return re.sub(
            r"[,.]?\s+(?:inc(?:orporated)?|corp(?:oration)?|co(?:mpany)?|ltd|limited|plc)\.?$",
            "",
            value,
            flags=re.IGNORECASE,
        ).strip()

    async def get_closest_candidates(self, query: str) -> List[Dict[str, Any]]:
        import difflib
        # Clean query
        query_clean = query.strip()
        query_lower = query_clean.lower()
        
        # 1. Private company check removed. Will fallback to Wikipedia if no candidate is found.

        ignored = {"deep", "analysis", "inc", "corp", "co", "ltd", "limited", "company"}
        query_words = [w for w in query_clean.split() if w.lower() not in ignored]
        search_term = query_words[0].lower() if query_words else query_lower
        
        # 2. Search Yahoo Finance with the simplified search term
        search_url = "https://query1.finance.yahoo.com/v1/finance/search"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        params = {
            "q": search_term,
            "quotesCount": 5,
            "newsCount": 0
        }
        quotes = []
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(search_url, params=params, headers=headers, timeout=5.0)
                if r.status_code == 200:
                    quotes = r.json().get("quotes", [])
        except Exception:
            pass
            
        candidates = []
        seen_tickers = set()
        
        # Process quotes from Yahoo Finance
        for q in quotes:
            symbol = q.get("symbol", "").upper()
            quote_type = q.get("quoteType", "").upper()
            long_name = q.get("longname", q.get("shortname", ""))
            if quote_type == "EQUITY" and symbol and long_name:
                first_word = long_name.lower().split()[0] if long_name.split() else ""
                ratio = difflib.SequenceMatcher(None, search_term, first_word).ratio()
                candidates.append({
                    "name": long_name,
                    "ticker": symbol,
                    "similarity": round(ratio, 2)
                })
                seen_tickers.add(symbol)
                
        # 3. Check local SEC tickers using the fast index
        if hasattr(self, 'sec_first_word_index') and self.sec_first_word_index:
            close_words = difflib.get_close_matches(search_term, self.sec_first_word_index.keys(), n=5, cutoff=0.5)
            for cw in close_words:
                for item in self.sec_first_word_index[cw]:
                    name = item["name"]
                    ticker = item["ticker"]
                    if ticker in seen_tickers:
                        continue
                    name_clean = name.lower()
                    first_word = name_clean.split()[0] if name_clean.split() else ""
                    ratio = difflib.SequenceMatcher(None, search_term, first_word).ratio()
                    if ticker.lower() == search_term:
                        ratio = 1.0
                    elif search_term in name_clean:
                        ratio = max(ratio, 0.7)
                        
                    if ratio > 0.4:
                        candidates.append({
                            "name": name,
                            "ticker": ticker,
                            "similarity": round(ratio, 2)
                        })
                        seen_tickers.add(ticker)
                        
        if not candidates:
            wiki_url = "https://en.wikipedia.org/w/api.php"
            wiki_params = {
                "action": "query",
                "list": "search",
                "srsearch": search_term,
                "format": "json"
            }
            wiki_headers = {
                "User-Agent": "MCPBusinessIntelligenceBot/1.0 (contact@mcp-business.com)"
            }
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.get(wiki_url, params=wiki_params, headers=wiki_headers, timeout=5.0)
                    if r.status_code == 200:
                        search_results = r.json().get("query", {}).get("search", [])
                        for result in search_results[:3]:
                            title = result.get("title")
                            if title:
                                title_clean = title.lower()
                                first_word = title_clean.split()[0] if title_clean.split() else ""
                                ratio = difflib.SequenceMatcher(None, search_term, first_word).ratio()
                                if search_term in title_clean:
                                    ratio = max(ratio, 0.7)
                                candidates.append({
                                    "name": title,
                                    "ticker": "PRIVATE",
                                    "similarity": round(ratio, 2)
                                })
            except Exception:
                pass

        # Sort and return top 3
        candidates.sort(key=lambda x: x["similarity"], reverse=True)
        return candidates[:3]

    async def resolve(self, query: str) -> EntityResolution:
        candidates = await self.get_candidates(query)
        return candidates[0]
