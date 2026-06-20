import math
from typing import Dict, Any, Optional

class AnalyticsCalculator:
    """
    Computes financial metrics (growth rates, CAGR, margins, debt ratios)
    using deterministic Python algorithms.
    """

    def calculate_cagr(self, history: Dict[str, Optional[float]], periods: list) -> Dict[str, float]:
        """
        Computes Compound Annual Growth Rate (CAGR) for N-year periods.
        """
        cagr_results = {}
        # Filter out empty or None values, sort years
        valid_history = {int(k): v for k, v in history.items() if v is not None and v > 0}
        if len(valid_history) < 2:
            return {}
            
        sorted_years = sorted(valid_history.keys())
        end_year = sorted_years[-1]
        end_val = valid_history[end_year]
        
        for n in periods:
            start_year = end_year - n
            if start_year in valid_history:
                start_val = valid_history[start_year]
                try:
                    cagr = ((end_val / start_val) ** (1.0 / n) - 1.0) * 100.0
                    cagr_results[f"{n}_year"] = round(cagr, 2)
                except Exception:
                    pass
        return cagr_results

    def calculate_yoy_growth(self, history: Dict[str, Optional[float]]) -> Dict[str, float]:
        """
        Computes Year-over-Year (YoY) growth rates.
        """
        yoy_results = {}
        valid_history = {int(k): v for k, v in history.items() if v is not None}
        sorted_years = sorted(valid_history.keys())
        
        for i in range(1, len(sorted_years)):
            prev_year = sorted_years[i - 1]
            curr_year = sorted_years[i]
            prev_val = valid_history[prev_year]
            curr_val = valid_history[curr_year]
            
            if prev_val is not None and prev_val != 0:
                growth = ((curr_val - prev_val) / abs(prev_val)) * 100.0
                yoy_results[str(curr_year)] = round(growth, 2)
                
        return yoy_results

    def calculate(self, sec_data: Dict[str, Any], yf_data: Dict[str, Any]) -> Dict[str, Any]:
        revenue_hist = sec_data.get("revenue_history", {})
        net_income_hist = sec_data.get("net_income_history", {})
        op_income_hist = sec_data.get("operating_income_history", {})
        assets_hist = sec_data.get("assets_history", {})
        liabilities_hist = sec_data.get("liabilities_history", {})
        
        # 1. CAGR
        cagr = self.calculate_cagr(revenue_hist, [3, 5, 10])
        
        # 2. YoY Revenue Growth
        rev_growth = self.calculate_yoy_growth(revenue_hist)
        
        # 3. YoY Profit Growth
        profit_growth = self.calculate_yoy_growth(net_income_hist)
        
        # 4. Debt-to-Equity Ratio
        debt_equity = None
        # Try to resolve latest year with both assets and liabilities from SEC
        valid_assets = {int(k): v for k, v in assets_hist.items() if v is not None}
        valid_liabilities = {int(k): v for k, v in liabilities_hist.items() if v is not None}
        common_years = sorted(set(valid_assets.keys()).intersection(valid_liabilities.keys()))
        
        if common_years:
            latest_year = common_years[-1]
            assets = valid_assets[latest_year]
            liabilities = valid_liabilities[latest_year]
            equity = assets - liabilities
            if equity > 0:
                debt_equity = round(liabilities / equity, 2)
                
        # Fallback to yfinance if SEC not available
        if debt_equity is None:
            # yfinance info often has debtToEquity (which is formatted as percentage e.g. 120.5 meaning 1.205)
            yf_de = yf_data.get("raw_data", {}).get("info", {}).get("debtToEquity")
            if yf_de is not None:
                debt_equity = round(yf_de / 100.0, 2)
                
        # 5. Operating Margin
        operating_margin = {}
        valid_rev = {int(k): v for k, v in revenue_hist.items() if v is not None and v != 0}
        valid_op = {int(k): v for k, v in op_income_hist.items() if v is not None}
        common_op_years = sorted(set(valid_rev.keys()).intersection(valid_op.keys()))
        
        for y in common_op_years:
            rev = valid_rev[y]
            op_inc = valid_op[y]
            operating_margin[str(y)] = round((op_inc / rev) * 100.0, 2)
            
        return {
            "revenue_growth": rev_growth,
            "profit_growth": profit_growth,
            "cagr": cagr,
            "debt_equity": debt_equity,
            "operating_margin": operating_margin
        }
