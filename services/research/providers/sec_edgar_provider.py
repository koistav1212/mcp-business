import httpx
from typing import Dict, Any, List, Optional
from services.research.base import BaseProvider

class SECEdgarProvider(BaseProvider):
    """
    Fetches official 10-K filing metrics from the SEC EDGAR CompanyFacts API.
    Supports 10 years of financial history for:
    - Revenue
    - Net Income
    - Assets
    - Liabilities
    - Operating Cash Flow
    - Shares Outstanding
    """

    def _get_sec_metric(self, facts: dict, concepts: list) -> Dict[str, float]:
        merged_by_year = {}
        # Try concepts in reverse order of priority, so higher priority overrides them
        for c in reversed(concepts):
            if c in facts:
                concept_data = facts[c]
                units = concept_data.get("units", {})
                if not units:
                    continue
                unit_key = list(units.keys())[0]
                entries = units[unit_key]
                
                # Filter for 10-K filings
                k_entries = [e for e in entries if e.get("form") == "10-K"]
                for e in k_entries:
                    fy = e.get("fy")
                    filed = e.get("filed", "")
                    val = e.get("val")
                    if fy is None or val is None:
                        continue
                    # Group by fiscal year (fy), picking the latest filed value
                    if fy not in merged_by_year or filed > merged_by_year[fy].get("filed", ""):
                        merged_by_year[fy] = e
                        
        # Sort by year, keep last 10 years
        sorted_years = sorted(merged_by_year.keys())
        last_10_years = sorted_years[-10:] if len(sorted_years) > 10 else sorted_years
        
        return {str(fy): float(merged_by_year[fy]["val"]) for fy in last_10_years}

    async def fetch(self, cik: Optional[str]) -> Dict[str, Any]:
        empty_data = {
            "revenue_history": {},
            "net_income_history": {},
            "operating_income_history": {},
            "assets_history": {},
            "liabilities_history": {},
            "cash_flow_history": {},
            "shares_outstanding_history": {},
            "buybacks_history": {},
            "dividends_history": {},
            "capex_history": {},
            "raw_data": {"note": "No CIK provided or private company."}
        }
        
        if not cik:
            return empty_data
            
        cik_str = str(cik).strip()
        # If it's a mock/private CIK
        if cik_str == "0000000000" or not cik_str.isdigit():
            # Placeholder CIK indicates unresolved or private entity — no EDGAR lookup possible.
            return empty_data

        cik_padded = cik_str.zfill(10)
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
        headers = {
            "User-Agent": "MCPBusinessIntelligenceBot/1.0 (contact@mcp-business.com)"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(url, headers=headers, timeout=10.0)
                if r.status_code == 200:
                    raw_data = r.json()
                    facts = raw_data.get("facts", {}).get("us-gaap", {})
                    
                    revenue = self._get_sec_metric(facts, [
                        "Revenues", 
                        "RevenueFromContractWithCustomerExcludingAssessedTax", 
                        "SalesRevenueNet", 
                        "SalesRevenueGoodsNet"
                    ])
                    net_income = self._get_sec_metric(facts, ["NetIncomeLoss"])
                    operating_income = self._get_sec_metric(facts, ["OperatingIncomeLoss", "OperatingProfitLoss"])
                    assets = self._get_sec_metric(facts, ["Assets"])
                    liabilities = self._get_sec_metric(facts, ["Liabilities"])
                    cash_flow = self._get_sec_metric(facts, ["NetCashProvidedByUsedInOperatingActivities"])
                    shares = self._get_sec_metric(facts, [
                        "CommonStockSharesOutstanding", 
                        "EntityCommonStockSharesOutstanding"
                    ])
                    
                    buybacks = self._get_sec_metric(facts, [
                        "PaymentsForRepurchaseOfCommonStock",
                        "PaymentsForRepurchaseOfTreasuryStock",
                        "StockRepurchaseProgramAuthorizedAmount"
                    ])
                    dividends = self._get_sec_metric(facts, [
                        "PaymentsOfDividends",
                        "PaymentsOfDividendsCommonStock",
                        "PaymentsOfDividendsMinorityInterest"
                    ])
                    capex = self._get_sec_metric(facts, [
                        "PaymentsToAcquirePropertyPlantAndEquipment",
                        "CapitalExpenditures",
                        "PaymentsToAcquirePropertyPlantAndEquipmentAndOtherIntangibleAssets"
                    ])
                    
                    return {
                        "revenue_history": revenue,
                        "net_income_history": net_income,
                        "operating_income_history": operating_income,
                        "assets_history": assets,
                        "liabilities_history": liabilities,
                        "cash_flow_history": cash_flow,
                        "shares_outstanding_history": shares,
                        "buybacks_history": buybacks,
                        "dividends_history": dividends,
                        "capex_history": capex,
                        "raw_data": {
                            "cik": cik_padded,
                            "entityName": raw_data.get("entityName")
                        }
                    }
                else:
                    return {
                        "revenue_history": {},
                        "net_income_history": {},
                        "operating_income_history": {},
                        "assets_history": {},
                        "liabilities_history": {},
                        "cash_flow_history": {},
                        "shares_outstanding_history": {},
                        "buybacks_history": {},
                        "dividends_history": {},
                        "capex_history": {},
                        "raw_data": {"error": f"SEC EDGAR returned status code {r.status_code}"}
                    }
        except Exception as e:
            return {
                "revenue_history": {},
                "net_income_history": {},
                "operating_income_history": {},
                "assets_history": {},
                "liabilities_history": {},
                "cash_flow_history": {},
                "shares_outstanding_history": {},
                "buybacks_history": {},
                "dividends_history": {},
                "capex_history": {},
                "raw_data": {"error": str(e)}
            }
