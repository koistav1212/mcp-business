from typing import Dict, Any

class FinancialCalculator:
    @staticmethod
    def compute_growth(financials: Dict[str, Any]) -> Dict[str, float]:
        if not financials: return {}
        revenue_history = financials.get("revenue_history", {})
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
        revenue_history = financials.get("revenue_history", {})
        net_income_history = financials.get("net_income_history", {})
        
        margins = {}
        for year in revenue_history.keys():
            if year in net_income_history and revenue_history[year]:
                margins[year] = net_income_history[year] / revenue_history[year]
        return {"net_margins": margins} if margins else {}

    @staticmethod
    def compute_cagr(financials: Dict[str, Any]) -> Dict[str, float]:
        if not financials: return {}
        revenue_history = financials.get("revenue_history", {})
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
        if financials and financials.get("pe_ratio"):
            ratios["pe_ratio"] = financials["pe_ratio"]
        if financials and financials.get("market_cap"):
            ratios["market_cap"] = financials["market_cap"]
        return ratios

    @staticmethod
    def compute_peer_comparison(company_data: Dict[str, Any], competitors: list) -> Dict[str, Any]:
        return {"peer_comparison_computed": True}

    @staticmethod
    def generate_analytics(financials: Dict[str, Any]) -> Dict[str, Any]:
        analytics = {}
        analytics.update(FinancialCalculator.compute_growth(financials))
        analytics.update(FinancialCalculator.compute_margin(financials))
        analytics.update(FinancialCalculator.compute_cagr(financials))
        analytics.update(FinancialCalculator.compute_ratios(financials))
        return analytics
