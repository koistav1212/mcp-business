# services/research/entity_resolver.py

import os
import json
import httpx
import re
from typing import List, Dict, Any, Optional

from services.research.models import EntityResolution, EntityCore


class EntityResolver:
    """
    Resolves free-text company queries to structured EntityResolution objects
    containing official name, ticker, CIK, exchange, website, and confidence.

    This resolver is designed to be the FIRST stage in the planner pipeline:
      Stage 1  – Normalize query (clean, lowercase, strip suffixes)
      Stage 2  – Alias lookup (future: custom alias maps for common short forms)
      Stage 3  – Ticker lookup (SEC, Yahoo Finance, NSE/BSE in future)
      Stage 4  – Exchange lookup (from quote metadata)
      Stage 5  – Official website discovery (SEC/Yahoo/Wikipedia + HTTP probing)
      Stage 6  – Wikipedia fallback (for private/unlisted companies)
      Stage 7  – OpenCorporates (TODO: corporate registry)
      Stage 8  – Crunchbase (TODO: startup/corporate profile)
      Stage 9  – LinkedIn (TODO: company page metadata)
      Stage 10 – GitHub (TODO: org/user presence)
      Stage 11 – Confidence scoring

    Downstream providers (news, technology stack, yfinance, Reddit, etc.) should
    only run AFTER this resolver has produced an EntityResolution with:
      - company_name (canonical display name)
      - ticker (if public)
      - exchange (if public)
      - website (best-effort official domain guess)
    """

    def __init__(self):
        self.tickers_cache_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "storage",
            "company_tickers.json",
        )
        self.sec_tickers: Dict[str, Dict[str, Any]] = {}
        self.sec_first_word_index: Dict[str, List[Dict[str, str]]] = {}
        # Try loading from local cache first
        self._load_cache()

    # ----------------------------------------------------------------------
    # SEC cache and indexing
    # ----------------------------------------------------------------------

    def _build_indexes(self) -> None:
        self.sec_first_word_index = {}
        for _, v in self.sec_tickers.items():
            title = v.get("title", "")
            ticker = v.get("ticker", "").upper()
            if title and ticker:
                title_clean = title.lower()
                words = title_clean.split()
                if words:
                    first_word = words[0]
                    lst = self.sec_first_word_index.setdefault(first_word, [])
                    lst.append({"name": title, "ticker": ticker})

    def _load_cache(self) -> None:
        if os.path.exists(self.tickers_cache_path):
            try:
                with open(self.tickers_cache_path, "r", encoding="utf-8") as f:
                    self.sec_tickers = json.load(f)
                self._build_indexes()
            except Exception:
                # If cache is corrupted, ignore it
                self.sec_tickers = {}

    async def _fetch_sec_tickers(self) -> Dict[str, Any]:
        """
        Load SEC company_tickers.json (US only). For Indian companies this will
        not help with ticker/CIK, but it is still useful for global names.
        """
        url = "https://www.sec.gov/files/company_tickers.json"
        headers = {
            "User-Agent": "MCPBusinessIntelligenceBot/1.0 (contact@mcp-business.com)",
        }
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(url, headers=headers, timeout=10.0)
                if r.status_code == 200:
                    data = r.json()
                    os.makedirs(os.path.dirname(self.tickers_cache_path), exist_ok=True)
                    with open(self.tickers_cache_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    self.sec_tickers = data
                    self._build_indexes()
                    return data
        except Exception:
            # Network or JSON errors: fall back to whatever we already have
            pass
        return self.sec_tickers

    # ----------------------------------------------------------------------
    # Core candidate resolution
    # ----------------------------------------------------------------------

    async def get_candidates(self, query: str) -> List[EntityResolution]:
        # Ensure we have the SEC tickers database loaded
        if not self.sec_tickers:
            await self._fetch_sec_tickers()

        # Clean query
        query_clean = query.strip()
        query_lower = query_clean.lower()

        # Stage 1: normalize company name
        normalized_query = self._normalize_company_name(query_clean)

        # Stage 3: SEC exact match before noisy remote search
        local_exact: List[EntityResolution] = []
        for value in self.sec_tickers.values():
            title = value.get("title", "")
            ticker = value.get("ticker", "").upper()
            if not title or not ticker:
                continue
            normalized_title = self._normalize_company_name(title)
            if normalized_query in {normalized_title, ticker.lower()}:
                display_name = self._display_company_name(title)
                # Stage 5: website discovery (initial guess, refined later)
                website_guess = await self._guess_website(display_name, ticker)
                
                # NEW: enrich with structured metadata
                meta = await self._enrich_company_metadata(
                    company_name=display_name,
                    ticker=ticker,
                    exchange=None,
                )
                
                # Build headquarters object if available
                hq_obj = None
                if meta.get("headquarters"):
                    parts = [p.strip() for p in meta["headquarters"].split(",")]
                    city = parts[0] if len(parts) > 0 else None
                    state = parts[1] if len(parts) > 1 else None
                    country = parts[2] if len(parts) > 2 else meta.get("country")
                    from services.research.models import Headquarters
                    hq_obj = Headquarters(city=city, state=state, country=country)

                local_exact.append(
                    EntityResolution(
                        entity=EntityCore(
                            name=display_name,
                            ticker=ticker,
                            cik=str(value.get("cik_str", "")).zfill(10) or None,
                            exchange=None,
                            website=website_guess,
                            legal_name=meta.get("legal_name") or display_name,
                            country=meta.get("country"),
                            headquarters=hq_obj,
                            industry=meta.get("industry"),
                            subindustry=meta.get("subindustry"),
                            founded=meta.get("founded"),
                            canonical_domain=self._canonical_domain_from_website(website_guess),
                            brand_names=[display_name],
                            aliases=[],
                        ),
                        official_pages=None,
                        social_profiles=None,
                        mobile_apps=[],
                        subsidiaries_or_brands=[],
                        metadata={
                            "confidence": 0.99,
                            "resolver_version": "1.0",
                            "source_type": "sec",
                            "last_verified": None,
                        },
                    )
                )

        # Stage 3/4: Yahoo Finance search
        search_url = "https://query1.finance.yahoo.com/v1/finance/search"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }
        params = {
            "q": query_clean,
            "quotesCount": 10,
            "newsCount": 0,
        }

        quotes: List[Dict[str, Any]] = []
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(search_url, params=params, headers=headers, timeout=10.0)
                if r.status_code == 200:
                    quotes = r.json().get("quotes", [])
        except Exception:
            # Yahoo can block or rate-limit; we degrade gracefully
            quotes = []

        candidates: List[EntityResolution] = []

        # Build SEC helper maps for ticker/name
        sec_by_ticker: Dict[str, Dict[str, Any]] = {}
        sec_by_name: Dict[str, Dict[str, Any]] = {}
        for _, v in self.sec_tickers.items():
            t = v.get("ticker", "").upper()
            c = str(v.get("cik_str", ""))
            n = v.get("title", "")
            if t:
                sec_by_ticker[t] = {"cik": c, "title": n}
            if n:
                sec_by_name[n.upper()] = {"cik": c, "ticker": t}

        # Process Yahoo quotes
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

            cik: Optional[str] = None
            resolved_name = long_name
            if sec_match:
                cik = sec_match["cik"].zfill(10)
                resolved_name = sec_match["title"] or resolved_name
            else:
                name_upper = long_name.upper()
                if name_upper in sec_by_name:
                    cik = sec_by_name[name_upper]["cik"].zfill(10)

            # Stage 11: confidence scoring
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
            if any(
                term in lower_name
                for term in [
                    "etf",
                    "etp",
                    "index",
                    "fund",
                    "tracker",
                    "shares 3x",
                    "daily target",
                ]
            ):
                confidence -= 0.5

            confidence = max(0.01, min(round(confidence, 2), 0.99))

            # Stage 5: website discovery using heuristic + HTTP probing
            website_guess = await self._guess_website(resolved_name, base_symbol)

            # NEW: enrich with structured metadata
            meta = await self._enrich_company_metadata(
                company_name=resolved_name,
                ticker=base_symbol,
                exchange=exchange,
            )

            # Build headquarters object if available
            hq_obj = None
            if meta.get("headquarters"):
                # crude split "City, State, Country"
                parts = [p.strip() for p in meta["headquarters"].split(",")]
                city = parts[0] if len(parts) > 0 else None
                state = parts[1] if len(parts) > 1 else None
                country = parts[2] if len(parts) > 2 else meta.get("country")
                from services.research.models import Headquarters  # adjust import path
                hq_obj = Headquarters(city=city, state=state, country=country)

            candidates.append(
                EntityResolution(
                    entity=EntityCore(
                        name=resolved_name,
                        ticker=symbol,
                        cik=cik,
                        exchange=exchange,
                        website=website_guess,
                        legal_name=meta.get("legal_name") or resolved_name,
                        country=meta.get("country"),
                        headquarters=hq_obj,
                        industry=meta.get("industry"),
                        subindustry=meta.get("subindustry"),
                        founded=meta.get("founded"),
                        canonical_domain=self._canonical_domain_from_website(website_guess),
                        brand_names=[resolved_name],
                        aliases=[],
                    ),
                    official_pages=None,
                    social_profiles=None,
                    mobile_apps=[],
                    subsidiaries_or_brands=[],
                    metadata={
                        "confidence": confidence,
                        "resolver_version": "1.0",
                        "source_type": "sec_yahoo_or_wiki",
                        "last_verified": None,
                    },
                )
            )

        # If Yahoo gave nothing but SEC exact matches exist, use those
        if not candidates and local_exact:
            candidates.extend(local_exact)

        # Stage 6: Wikipedia fallback for private/unlisted/non-US companies
        if not candidates:
            wiki_candidate = await self._wikipedia_fallback(query_clean)
            if wiki_candidate:
                candidates.append(wiki_candidate)

        # If still nothing, create a very low-confidence guess
        if not candidates:
            website_guess = await self._guess_website(query_clean, None)
            
            # NEW: enrich with structured metadata
            meta = await self._enrich_company_metadata(
                company_name=query.capitalize(),
                ticker=None,
                exchange="UNKNOWN",
            )
            
            # Build headquarters object if available
            hq_obj = None
            if meta.get("headquarters"):
                parts = [p.strip() for p in meta["headquarters"].split(",")]
                city = parts[0] if len(parts) > 0 else None
                state = parts[1] if len(parts) > 1 else None
                country = parts[2] if len(parts) > 2 else meta.get("country")
                from services.research.models import Headquarters
                hq_obj = Headquarters(city=city, state=state, country=country)

            candidates.append(
                EntityResolution(
                    entity=EntityCore(
                        name=query.capitalize(),
                        ticker=None,
                        cik=None,
                        exchange="UNKNOWN",
                        website=website_guess,
                        legal_name=meta.get("legal_name") or query.capitalize(),
                        country=meta.get("country"),
                        headquarters=hq_obj,
                        industry=meta.get("industry"),
                        subindustry=meta.get("subindustry"),
                        founded=meta.get("founded"),
                        canonical_domain=self._canonical_domain_from_website(website_guess),
                        brand_names=[query.capitalize()],
                        aliases=[],
                    ),
                    official_pages=None,
                    social_profiles=None,
                    mobile_apps=[],
                    subsidiaries_or_brands=[],
                    metadata={
                        "confidence": 0.1,
                        "resolver_version": "1.0",
                        "source_type": "fallback",
                        "last_verified": None,
                    },
                )
            )

        candidates.sort(key=lambda x: x.confidence, reverse=True)
        return candidates

    # ----------------------------------------------------------------------
    # Normalization and display helpers
    # ----------------------------------------------------------------------

    @staticmethod
    def _normalize_company_name(value: str) -> str:
        cleaned = re.sub(r"[^a-z0-9\s]", " ", value.lower())
        words = cleaned.split()
        suffixes = {
            "inc",
            "incorporated",
            "corp",
            "corporation",
            "co",
            "company",
            "ltd",
            "limited",
            "plc",
        }
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

    # ----------------------------------------------------------------------
    # Website discovery (Stage 5)
    # ----------------------------------------------------------------------

    async def _guess_website(self, company_name: str, ticker: Optional[str]) -> str:
        """
        Guess and validate a company website domain.

        Strategy:
          - Generate several candidate domains:
              * ticker-based: {ticker}.com (if alpha)
              * name-based: joined words, no suffixes: relianceindustries.com, hdfcbank.com
              * first-word-based: reliance.com, tcs.com
          - Try HTTPS for each candidate and pick the first that responds with 200–399.
          - If none resolve, fall back to the simplest name-based guess.

        This works better for Indian companies like:
          - "Reliance Industries Limited"  -> relianceindustries.com
          - "HDFC Bank"                    -> hdfcbank.com
          - "Tata Consultancy Services"    -> tataconsultancyservices.com
        than the original "first word only" heuristic.
        """
        name_norm = self._normalize_company_name(company_name)
        words = name_norm.split()
        candidates: List[str] = []

        # ticker-based domain
        if ticker and ticker.isalpha():
            candidates.append(f"{ticker.lower()}.com")

        # full name collapsed (no spaces)
        if words:
            collapsed = "".join(words)
            candidates.append(f"{collapsed}.com")

        # first word only
        if words:
            candidates.append(f"{words[0]}.com")

        # generic fallback: raw name without spaces/punctuation
        raw = re.sub(r"[^a-z0-9]", "", name_norm)
        if raw:
            candidates.append(f"{raw}.com")

        # Deduplicate candidates preserving order
        seen: set = set()
        unique_candidates: List[str] = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                unique_candidates.append(c)

        # Try probing each candidate via HTTPS HEAD/GET
        for domain in unique_candidates:
            url = f"https://{domain}"
            try:
                async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                    r = await client.get(url)
                    if 200 <= r.status_code < 400:
                        return domain
            except Exception:
                # Connection errors are expected for wrong guesses; ignore
                continue

        # None resolved; return the first candidate as a best-effort guess
        return unique_candidates[0] if unique_candidates else f"{name_norm.replace(' ', '')}.com"

    @staticmethod
    def _canonical_domain_from_website(website: Optional[str]) -> Optional[str]:
        if not website:
            return None
        try:
            parsed = httpx.URL(website)  # or urllib.parse.urlparse
            host = parsed.host or parsed.netloc
            # strip 'www.' prefix
            if host.startswith("www."):
                host = host[4:]
            return host
        except Exception:
            return None

    # ----------------------------------------------------------------------
    # Company metadata enrichment (industry, country, HQ, founded)
    # ----------------------------------------------------------------------

    async def _enrich_company_metadata(
        self,
        company_name: str,
        ticker: Optional[str],
        exchange: Optional[str],
    ) -> Dict[str, Any]:
        """
        Fetch structured company metadata (industry, subindustry, country,
        headquarters, founded) from external sources (e.g., Yahoo assetProfile).
        """
        meta: Dict[str, Any] = {
            "industry": None,
            "subindustry": None,
            "country": None,
            "headquarters": None,
            "founded": None,
            "legal_name": None,
        }

        # If we have a ticker, try Yahoo assetProfile
        if ticker:
            try:
                profile_url = (
                    "https://query1.finance.yahoo.com/v10/finance/quoteSummary/"
                    f"{ticker}"
                )
                params = {"modules": "assetProfile"}
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/91.0.4472.124 Safari/537.36"
                    )
                }
                async with httpx.AsyncClient() as client:
                    r = await client.get(profile_url, params=params, headers=headers, timeout=10.0)
                    if r.status_code == 200:
                        data = r.json()
                        profile = (
                            data.get("quoteSummary", {})
                            .get("result", [{}])[0]
                            .get("assetProfile", {})
                        )
                        meta["industry"] = profile.get("industry")
                        # you can store sector as subindustry for now
                        meta["subindustry"] = profile.get("sector")
                        meta["country"] = profile.get("country")

                        city = profile.get("city")
                        state = profile.get("state")
                        hq_parts = [p for p in [city, state, meta["country"]] if p]
                        if hq_parts:
                            meta["headquarters"] = ", ".join(hq_parts)

                        # foundedYear sometimes available as 'fullTimeEmployees' etc.,
                        # but some APIs have 'foundedYear' – placeholder here:
                        meta["founded"] = profile.get("foundedYear")
                        meta["legal_name"] = company_name
            except Exception:
                # silent fail; we keep defaults
                pass

        return meta

    # ----------------------------------------------------------------------
    # Wikipedia fallback (Stage 6)
    # ----------------------------------------------------------------------

    async def _wikipedia_fallback(self, query_clean: str) -> Optional[EntityResolution]:
        wiki_url = "https://en.wikipedia.org/w/api.php"
        wiki_params = {
            "action": "query",
            "list": "search",
            "srsearch": query_clean,
            "format": "json",
        }
        wiki_headers = {
            "User-Agent": "MCPBusinessIntelligenceBot/1.0 (contact@mcp-business.com)",
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
                            first_word = title.lower().split()[0].replace(",", "").replace(".", "")
                            website_guess = await self._guess_website(title, None)
                            
                            # NEW: enrich with structured metadata
                            meta = await self._enrich_company_metadata(
                                company_name=title,
                                ticker=None,
                                exchange="PRIVATE",
                            )
                            
                            # Build headquarters object if available
                            hq_obj = None
                            if meta.get("headquarters"):
                                parts = [p.strip() for p in meta["headquarters"].split(",")]
                                city = parts[0] if len(parts) > 0 else None
                                state = parts[1] if len(parts) > 1 else None
                                country = parts[2] if len(parts) > 2 else meta.get("country")
                                from services.research.models import Headquarters
                                hq_obj = Headquarters(city=city, state=state, country=country)

                            return EntityResolution(
                                entity=EntityCore(
                                    name=title,
                                    ticker=None,
                                    cik=None,
                                    exchange="PRIVATE",
                                    website=website_guess,
                                    legal_name=meta.get("legal_name") or title,
                                    country=meta.get("country"),
                                    headquarters=hq_obj,
                                    industry=meta.get("industry"),
                                    subindustry=meta.get("subindustry"),
                                    founded=meta.get("founded"),
                                    canonical_domain=self._canonical_domain_from_website(website_guess),
                                    brand_names=[title],
                                    aliases=[],
                                ),
                                official_pages=None,
                                social_profiles=None,
                                mobile_apps=[],
                                subsidiaries_or_brands=[],
                                metadata={
                                    "confidence": 0.85,
                                    "resolver_version": "1.0",
                                    "source_type": "wikipedia",
                                    "last_verified": None,
                                },
                            )
        except Exception:
            return None
        return None

    # ----------------------------------------------------------------------
    # Closest ticker + name suggestions (for UI)
    # ----------------------------------------------------------------------

    async def get_closest_candidates(self, query: str) -> List[Dict[str, Any]]:
        import difflib

        query_clean = query.strip()
        query_lower = query_clean.lower()

        ignored = {"deep", "analysis", "inc", "corp", "co", "ltd", "limited", "company"}
        query_words = [w for w in query_clean.split() if w.lower() not in ignored]
        search_term = query_words[0].lower() if query_words else query_lower

        # Yahoo Finance quick search
        search_url = "https://query1.finance.yahoo.com/v1/finance/search"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }
        params = {
            "q": search_term,
            "quotesCount": 5,
            "newsCount": 0,
        }
        quotes: List[Dict[str, Any]] = []
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(search_url, params=params, headers=headers, timeout=5.0)
                if r.status_code == 200:
                    quotes = r.json().get("quotes", [])
        except Exception:
            quotes = []

        candidates: List[Dict[str, Any]] = []
        seen_tickers: set = set()

        # Process quotes
        for q in quotes:
            symbol = q.get("symbol", "").upper()
            quote_type = q.get("quoteType", "").upper()
            long_name = q.get("longname", q.get("shortname", ""))
            if quote_type == "EQUITY" and symbol and long_name:
                first_word = long_name.lower().split()[0] if long_name.split() else ""
                ratio = difflib.SequenceMatcher(None, search_term, first_word).ratio()
                candidates.append({"name": long_name, "ticker": symbol, "similarity": round(ratio, 2)})
                seen_tickers.add(symbol)

        # SEC index suggestions
        if hasattr(self, "sec_first_word_index") and self.sec_first_word_index:
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
                        candidates.append({"name": name, "ticker": ticker, "similarity": round(ratio, 2)})
                        seen_tickers.add(ticker)

        # Wikipedia suggestions if nothing found
        if not candidates:
            wiki_url = "https://en.wikipedia.org/w/api.php"
            wiki_params = {
                "action": "query",
                "list": "search",
                "srsearch": search_term,
                "format": "json",
            }
            wiki_headers = {
                "User-Agent": "MCPBusinessIntelligenceBot/1.0 (contact@mcp-business.com)",
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
                                candidates.append(
                                    {"name": title, "ticker": "PRIVATE", "similarity": round(ratio, 2)}
                                )
            except Exception:
                pass

        candidates.sort(key=lambda x: x["similarity"], reverse=True)
        return candidates[:3]

    # ----------------------------------------------------------------------
    # Simple resolve wrapper
    # ----------------------------------------------------------------------

    async def resolve(self, query: str) -> EntityResolution:
        candidates = await self.get_candidates(query)
        return candidates[0]