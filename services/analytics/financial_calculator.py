from typing import Dict, Any

class FinancialCalculator:
    @staticmethod
    def _get_val(financials: Dict[str, Any], key: str) -> Any:
        val = financials.get(key)
        if isinstance(val, dict) and "value" in val:
            return val["value"]
        return val

    @staticmethod
    def compute_growth(financials: Dict[str, Any]) -> Dict[str, float]:
        if not financials: return {}
        revenue_history = FinancialCalculator._get_val(financials, "revenue_history") or {}
        if not revenue_history or len(revenue_history) < 2: return {}
        
        years = sorted(revenue_history.keys())
        latest = revenue_history[years[-1]]
        previous = revenue_history[years[-2]]
        
        if previous and previous > 0:
            return {"revenue_yoy": (latest - previous) / previous}
        return {}

    @staticmethod
    def compute_margin(financials: Dict[str, Any]) -> Dict[str, float]:
        if not financials: return {}
        revenue_history = FinancialCalculator._get_val(financials, "revenue_history") or {}
        net_income_history = FinancialCalculator._get_val(financials, "net_income_history") or {}
        
        margins = {}
        for year in revenue_history.keys():
            if year in net_income_history and revenue_history[year]:
                margins[year] = net_income_history[year] / revenue_history[year]
        return {"net_margins": margins} if margins else {}

    @staticmethod
    def compute_cagr(financials: Dict[str, Any]) -> Dict[str, float]:
        if not financials: return {}
        revenue_history = FinancialCalculator._get_val(financials, "revenue_history") or {}
        if not revenue_history or len(revenue_history) < 2: return {}
        
        years = sorted(revenue_history.keys())
        start_year = years[0]
        end_year = years[-1]
        start_val = revenue_history[start_year]
        end_val = revenue_history[end_year]
        
        periods = int(end_year) - int(start_year) if end_year.isdigit() and start_year.isdigit() else len(years) - 1
        
        if start_val and start_val > 0 and periods > 0:
            cagr = (end_val / start_val) ** (1 / periods) - 1
            return {f"{periods}_year_cagr": cagr}
        return {}

    @staticmethod
    def compute_ratios(financials: Dict[str, Any]) -> Dict[str, float]:
        # Return basic ratios like pe_ratio if available
        ratios = {}
        pe_ratio = FinancialCalculator._get_val(financials, "pe_ratio")
        if pe_ratio is not None:
            ratios["pe_ratio"] = pe_ratio
        market_cap = FinancialCalculator._get_val(financials, "market_cap")
        if market_cap is not None:
            ratios["market_cap"] = market_cap
        return ratios

    @staticmethod
    def compute_peer_comparison(company_data: Dict[str, Any], competitors: list) -> Dict[str, Any]:
        return {"peer_comparison_computed": True}

    @staticmethod
    def generate_analytics(financials: Dict[str, Any]) -> Dict[str, Any]:
        analytics = {
            "revenue_growth": {},
            "profit_growth": {},
            "cagr": {},
            "debt_equity": None,
            "operating_margin": {},
            "net_margin": {},
            "fcf_margin": {},
            "roa": {},
            "roe": {},
            "interest_coverage": {}
        }
        
        growth = FinancialCalculator.compute_growth(financials)
        if "revenue_yoy" in growth:
            analytics["revenue_growth"]["YoY"] = growth["revenue_yoy"]
            
        margins = FinancialCalculator.compute_margin(financials)
        if "net_margins" in margins:
            analytics["net_margin"] = margins["net_margins"]
            
        cagr = FinancialCalculator.compute_cagr(financials)
        analytics["cagr"] = cagr
        
        de = FinancialCalculator._get_val(financials, "debt_to_equity")
        if de is not None:
            try: analytics["debt_equity"] = float(de)
            except Exception: pass
            
        roa = FinancialCalculator._get_val(financials, "return_on_assets")
        if roa is not None:
            try: analytics["roa"]["current"] = float(roa)
            except Exception: pass
            
        roe = FinancialCalculator._get_val(financials, "return_on_equity")
        if roe is not None:
            try: analytics["roe"]["current"] = float(roe)
            except Exception: pass
            
        op_margin = FinancialCalculator._get_val(financials, "operating_margin_ttm")
        if op_margin is not None:
            try: analytics["operating_margin"]["TTM"] = float(op_margin)
            except Exception: pass
            
        return analytics
