import asyncio
from datetime import datetime, timezone
from typing import Any, List

import yfinance as yf

from services.research.base import BaseProvider
from services.knowledge.evidence import ResearchEvidence
from services.research.providers.shared_utils import _clean_nan, _write_json, _emit, logger

class YFinanceProvider(BaseProvider):
    """
    Live market data from Yahoo Finance via yfinance.
    """
    async def fetch(self, target: Any) -> List[ResearchEvidence]:
        ticker_symbol = self._extract_identifier(target)
        if not ticker_symbol:
            return []
        ticker_clean = str(ticker_symbol).strip().upper()
        if "MOCK" in ticker_clean or "PRIVATE" in ticker_clean:
            return []
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        evidence_list: List[ResearchEvidence] = []
        try:
            loop = asyncio.get_event_loop()
            ticker_obj = yf.Ticker(ticker_clean)
            info = await loop.run_in_executor(None, lambda: ticker_obj.info or {})
            info = _clean_nan(info)

            recommendations = None
            try:
                recs = await loop.run_in_executor(None, lambda: ticker_obj.recommendations)
                if recs is not None and not recs.empty:
                    recent = recs.tail(5)
                    recommendations = recent.to_dict("records")
            except Exception:
                pass

            institutions = None
            try:
                inst = await loop.run_in_executor(None, lambda: ticker_obj.institutional_holders)
                if inst is not None and not inst.empty:
                    institutions = inst.head(10).to_dict("records")
            except Exception:
                pass

            _write_json(f"yfinance_{ticker_clean}.json", {
                "info_keys": list(info.keys()),
                "recommendations_count": len(recommendations) if recommendations else 0,
            })

            field_map = {
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "ps_ratio": info.get("priceToSalesTrailing12Months"),
                "pb_ratio": info.get("priceToBook"),
                "peg_ratio": info.get("pegRatio"),
                "ev_ebitda": info.get("enterpriseToEbitda"),
                "ev_revenue": info.get("enterpriseToRevenue"),
                "current_price": (
                    info.get("currentPrice")
                    or info.get("regularMarketPrice")
                    or info.get("regularMarketPreviousClose")
                ),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                "fifty_day_average": info.get("fiftyDayAverage"),
                "two_hundred_day_average": info.get("twoHundredDayAverage"),
                "beta": info.get("beta"),
                "dividend_yield": info.get("dividendYield"),
                "earnings_per_share": info.get("trailingEps"),
                "forward_eps": info.get("forwardEps"),
                "book_value_per_share": info.get("bookValue"),
                "analyst_target_price": info.get("targetMeanPrice"),
                "analyst_target_high": info.get("targetHighPrice"),
                "analyst_target_low": info.get("targetLowPrice"),
                "analyst_recommendation": info.get("recommendationKey"),
                "analyst_count": info.get("numberOfAnalystOpinions"),
                "analyst_strong_buy": info.get("recommendationMean"),
                "institutional_ownership_pct": info.get("heldPercentInstitutions"),
                "insider_ownership_pct": info.get("heldPercentInsiders"),
                "short_interest_pct": info.get("shortPercentOfFloat"),
                "shares_short": info.get("sharesShort"),
                "revenue_ttm": info.get("totalRevenue"),
                "net_income_ttm": info.get("netIncomeToCommon"),
                "ebitda_ttm": info.get("ebitda"),
                "free_cash_flow_ttm": info.get("freeCashflow"),
                "total_cash": info.get("totalCash"),
                "total_debt": info.get("totalDebt"),
                "debt_to_equity": info.get("debtToEquity"),
                "return_on_equity": info.get("returnOnEquity"),
                "return_on_assets": info.get("returnOnAssets"),
                "profit_margin": info.get("profitMargins"),
                "operating_margin_ttm": info.get("operatingMargins"),
                "gross_margin": info.get("grossMargins"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "full_time_employees": info.get("fullTimeEmployees"),
                "long_business_summary": (info.get("longBusinessSummary") or "")[:600],
                "country": info.get("country"),
                "city": info.get("city"),
                "exchange": info.get("exchange"),
            }

            for attr, val in field_map.items():
                if val is None:
                    continue
                conf = 0.95 if attr in ("market_cap", "current_price", "pe_ratio") else 0.88
                _emit(
                    evidence_list,
                    entity=ticker_clean,
                    attribute=attr,
                    value=val,
                    source="yfinance",
                    source_type="mcp",
                    confidence=conf,
                    now_str=now_str,
                    source_url=f"https://finance.yahoo.com/quote/{ticker_clean}",
                )

            if recommendations:
                _emit(
                    evidence_list,
                    entity=ticker_clean,
                    attribute="analyst_recommendations_history",
                    value=recommendations,
                    source="yfinance",
                    source_type="mcp",
                    confidence=0.85,
                    now_str=now_str,
                )

            if institutions:
                _emit(
                    evidence_list,
                    entity=ticker_clean,
                    attribute="institutional_holders",
                    value=institutions,
                    source="yfinance",
                    source_type="mcp",
                    confidence=0.85,
                    now_str=now_str,
                )

        except Exception as exc:
            logger.warning(f"YFinanceProvider failed for {ticker_clean}: {exc}")

        _write_json(
            f"yfinance_evidence_{ticker_clean}.json",
            [e.model_dump(mode='json') for e in evidence_list],
        )
        logger.info(f"YFinanceProvider: {len(evidence_list)} evidence items for {ticker_clean}")
        return evidence_list
