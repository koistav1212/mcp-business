from typing import Dict, Any, List

class FinancialNormalizer:
    """
    Normalizes financial metrics from multiple providers into a single canonical GAAP schema.
    Eliminates conflicts like `cash` vs `cashflow` vs `cash_flow`.
    """
    
    @staticmethod
    def normalize_balance_sheet(data: Dict[str, Any]) -> Dict[str, Any]:
        normalized = {}
        # Cash & Equivalents
        normalized["cash_and_cash_equivalents"] = (
            data.get("cash_and_cash_equivalents") or 
            data.get("total_cash") or 
            data.get("cash") or 
            data.get("cash_and_equivalents")
        )
        # Total Debt
        normalized["total_debt"] = (
            data.get("total_debt") or 
            data.get("debt") or 
            data.get("long_term_debt")
        )
        return {k: v for k, v in normalized.items() if v is not None}

    @staticmethod
    def normalize_cashflow(data: Dict[str, Any]) -> Dict[str, Any]:
        normalized = {}
        # Free Cash Flow
        normalized["free_cash_flow"] = (
            data.get("free_cash_flow") or 
            data.get("free_cash_flow_ttm") or 
            data.get("cashflow") or 
            data.get("cash_flow")
        )
        return {k: v for k, v in normalized.items() if v is not None}

    @staticmethod
    def normalize_income_statement(data: Dict[str, Any]) -> Dict[str, Any]:
        normalized = {}
        # Revenue
        normalized["revenue"] = (
            data.get("revenue") or 
            data.get("total_revenue") or 
            data.get("revenue_ttm")
        )
        # Net Income
        normalized["net_income"] = (
            data.get("net_income") or 
            data.get("net_income_ttm") or 
            data.get("net_income_to_common")
        )
        # Gross Margin
        normalized["gross_margin"] = (
            data.get("gross_margin") or 
            data.get("gross_margins")
        )
        # Operating Margin
        normalized["operating_margin"] = (
            data.get("operating_margin") or 
            data.get("operating_margins") or 
            data.get("operating_margin_ttm")
        )
        return {k: v for k, v in normalized.items() if v is not None}

    @staticmethod
    def normalize_market_metrics(data: Dict[str, Any]) -> Dict[str, Any]:
        normalized = {}
        # Market Capitalization
        normalized["market_capitalization"] = (
            data.get("market_capitalization") or 
            data.get("market_cap")
        )
        return {k: v for k, v in normalized.items() if v is not None}

    @classmethod
    def merge_financial_metrics(cls, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Takes raw fields (e.g. from yfinance) and maps them to the canonical GAAP schema.
        """
        bs = cls.normalize_balance_sheet(raw_data)
        cf = cls.normalize_cashflow(raw_data)
        inc = cls.normalize_income_statement(raw_data)
        mkt = cls.normalize_market_metrics(raw_data)
        
        merged = {}
        merged.update(bs)
        merged.update(cf)
        merged.update(inc)
        merged.update(mkt)
        
        # Keep non-colliding fields
        for k, v in raw_data.items():
            if k not in ["cash", "total_cash", "debt", "total_debt", "cashflow", "cash_flow", "free_cash_flow_ttm", "revenue_ttm", "total_revenue", "net_income_ttm", "net_income_to_common", "gross_margins", "operating_margins", "operating_margin_ttm", "market_cap"]:
                if k not in merged:
                    merged[k] = v

        return merged
