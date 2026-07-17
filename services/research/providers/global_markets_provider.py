import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from services.research.base import BaseProvider
from services.knowledge.evidence import ResearchEvidence
from services.research.providers.shared_utils import _BOT_UA, _get, _emit, _write_json, logger


class GlobalMarketsProvider(BaseProvider):
    """
    Fetches standardized financial data for global listed companies
    (US + non-US) using ticker/exchange-based APIs, and falls back
    to lightweight estimates for some private firms where available.

    """

    _HEADERS = {"User-Agent": _BOT_UA, "Accept-Encoding": "gzip, deflate"}

    # Common metric keys aligned with your FinancialData schema.
    _METRICS: Dict[str, str] = {
        "revenue_history":        "revenue",
        "net_income_history":     "net_income",
        "operating_income_history": "operating_income",
        "gross_profit_history":   "gross_profit",
        "assets_history":         "total_assets",
        "liabilities_history":    "total_liabilities",
        "equity_history":         "total_equity",
        "cash_flow_history":      "operating_cash_flow",
        "free_cash_flow_history": "free_cash_flow",
        "shares_outstanding_history": "shares_outstanding",
        "buybacks_history":       "share_buybacks",
        "dividends_history":      "dividends_paid",
        "capex_history":          "capital_expenditures",
        "rd_expense_history":     "research_and_development_expense",
        "interest_expense_history": "interest_expense",
        "long_term_debt_history": "long_term_debt",
    }

    def _extract_ticker(self, target: Any) -> Optional[str]:
        if hasattr(target, "ticker") and target.ticker:
            return str(target.ticker)
        if isinstance(target, dict):
            return str(target.get("ticker", "")).upper()
        return None

    def _extract_exchange(self, target: Any) -> Optional[str]:
        if hasattr(target, "exchange") and target.exchange:
            return str(target.exchange)
        if isinstance(target, dict):
            return str(target.get("exchange", ""))
        return None

    async def _fetch_listed_fundamentals(
        self, client: httpx.AsyncClient, ticker: str, exchange: Optional[str]
    ) -> Dict[str, Dict[str, float]]:
        """
        Fetch time series financials for a listed company from a global markets API.
        This is a stub; you must integrate your real data source here.

        Return format:
        {
          "revenue": {"2022": 1.23e9, "2023": 1.45e9},
          "net_income": {"2022": 2.1e8, "2023": 2.4e8},
          ...
        }
        """
        # Example stub using your own MCP tool or a 3rd-party API:
        # url = f"https://your-global-api/fundamentals/{exchange}/{ticker}"
        # r = await _get(client, url, headers=self._HEADERS)
        # if not r:
        #     return {}
        # data = r.json()
        # return data.get("timeseries", {})
        return {}

    async def _fetch_private_estimates(
        self, client: httpx.AsyncClient, company_name: str, country: Optional[str]
    ) -> Dict[str, Dict[str, float]]:
        """
        For private companies, try to get approximate or last-known financials
        from a private-company dataset (Crunchbase-like, S&P Private Company
        Financials, etc.). For many firms this may be sparse or missing. [web:273][web:281]

        Return format same as _fetch_listed_fundamentals.
        """
        # Example stub:
        # url = f"https://your-private-financials-api/search"
        # payload = {"name": company_name, "country": country}
        # r = await client.post(url, json=payload, headers=self._HEADERS)
        # ...
        return {}

    async def _resolve_ticker_and_exchange(self, company_name: str) -> tuple[Optional[str], Optional[str]]:
        search_url = "https://query1.finance.yahoo.com/v1/finance/search"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }
        params = {"q": company_name, "quotesCount": 1, "newsCount": 0}
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(search_url, params=params, headers=headers, timeout=5.0)
                if r.status_code == 200:
                    quotes = r.json().get("quotes", [])
                    for q in quotes:
                        if q.get("quoteType") == "EQUITY":
                            return q.get("symbol"), (q.get("exchDisp") or q.get("exchange"))
        except Exception:
            pass
            
        static_map = {
            "nvidia": ("NVDA", "NASDAQ"), "apple": ("AAPL", "NASDAQ"), 
            "microsoft": ("MSFT", "NASDAQ"), "google": ("GOOGL", "NASDAQ"), 
            "alphabet": ("GOOGL", "NASDAQ"), "amazon": ("AMZN", "NASDAQ"), 
            "meta": ("META", "NASDAQ"), "tesla": ("TSLA", "NASDAQ")
        }
        return static_map.get(company_name.lower(), (None, None))

    async def fetch(self, target: Any) -> List[ResearchEvidence]:
        """
        Main entrypoint: decide whether to treat the company as listed
        (ticker + exchange) or private, then emit ResearchEvidence with
        standardized histories for consulting-style analysis.
        """
        ticker_symbol = self._extract_identifier(target, preferred_key="ticker")
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        evidence_list: List[ResearchEvidence] = []

        ticker = self._extract_ticker(target)
        exchange = self._extract_exchange(target)
        company_name = getattr(target, "name", None) or \
                       (target.get("name") if isinstance(target, dict) else None)
        if not company_name and isinstance(target, str):
            company_name = target
            
        country = getattr(target, "country", None) or \
                  (target.get("country") if isinstance(target, dict) else None)

        if not ticker and company_name:
            resolved_ticker, resolved_exchange = await self._resolve_ticker_and_exchange(company_name)
            if resolved_ticker:
                ticker = resolved_ticker
            if resolved_exchange and not exchange:
                exchange = resolved_exchange

        async with httpx.AsyncClient(headers=self._HEADERS, timeout=20.0) as client:
            timeseries: Dict[str, Dict[str, float]] = {}

            # Case 1: global listed companies (NYSE, NASDAQ, LSE, NSE, HKEX, etc.)
            if ticker and exchange:
                timeseries = await self._fetch_listed_fundamentals(client, ticker, exchange)

            # Case 2: global private or non-listed companies – attempt estimates
            elif company_name:
                timeseries = await self._fetch_private_estimates(client, company_name, country)

            if not timeseries:
                logger.info(f"GlobalMarketsProvider: no timeseries for {company_name or ticker}")
                return []

            # Emit evidence in your common schema
            for attr, key in self._METRICS.items():
                history = timeseries.get(key)
                if history:
                    _emit(
                        evidence_list,
                        entity=company_name or ticker,
                        attribute=attr,
                        value=history,
                        source="global_markets",
                        source_type="mcp",
                        confidence=0.9,
                        now_str=now_str,
                        # fill in your actual source URL if you have one
                        source_url=None,
                    )

        _write_json(
            f"global_markets_evidence_{(ticker or company_name or 'unknown')}.json",
            [e.model_dump(mode="json") for e in evidence_list],
        )
        logger.info(
            f"GlobalMarketsProvider: {len(evidence_list)} evidence items for "
            f"{ticker or company_name}"
        )
        return evidence_list
