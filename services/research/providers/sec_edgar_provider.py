import httpx
from typing import Dict, Any, List, Optional
from services.research.base import BaseProvider
from services.knowledge.evidence import ResearchEvidence
from services.knowledge.citation_manager import CitationManager

class SECEdgarProvider(BaseProvider):
    """
    Fetches official 10-K filing metrics from the SEC EDGAR CompanyFacts API.
    Returns typed ResearchEvidence lists.
    """

    def _get_sec_metric(self, facts: dict, concepts: list) -> Dict[str, float]:
        merged_by_year = {}
        for c in reversed(concepts):
            if c in facts:
                concept_data = facts[c]
                units = concept_data.get("units", {})
                if not units:
                    continue
                unit_key = list(units.keys())[0]
                entries = units[unit_key]
                
                k_entries = [e for e in entries if e.get("form") == "10-K"]
                for e in k_entries:
                    fy = e.get("fy")
                    filed = e.get("filed", "")
                    val = e.get("val")
                    if fy is None or val is None:
                        continue
                    if fy not in merged_by_year or filed > merged_by_year[fy].get("filed", ""):
                        merged_by_year[fy] = e
                        
        sorted_years = sorted(merged_by_year.keys())
        last_10_years = sorted_years[-10:] if len(sorted_years) > 10 else sorted_years
        return {str(fy): float(merged_by_year[fy]["val"]) for fy in last_10_years}

    def _extract_cik(self, target: Any) -> Optional[str]:
        if not target:
            return None
        if hasattr(target, "cik") and target.cik:
            return target.cik
        if isinstance(target, dict) and target.get("cik"):
            return target.get("cik")
        return str(target)

    async def fetch(self, target: Any) -> List[ResearchEvidence]:
        cik = self._extract_cik(target)
        if not cik:
            return []
            
        cik_str = str(cik).strip()
        if cik_str == "0000000000" or not cik_str.isdigit():
            return []

        cik_padded = cik_str.zfill(10)
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
        headers = {
            "User-Agent": "MCPBusinessIntelligenceBot/1.0 (contact@mcp-business.com)"
        }
        
        evidence_list = []
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(url, headers=headers, timeout=10.0)
                if r.status_code == 200:
                    raw_data = r.json()
                    facts = raw_data.get("facts", {}).get("us-gaap", {})
                    
                    data_map = {
                        "revenue_history": self._get_sec_metric(facts, ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "SalesRevenueGoodsNet"]),
                        "net_income_history": self._get_sec_metric(facts, ["NetIncomeLoss"]),
                        "operating_income_history": self._get_sec_metric(facts, ["OperatingIncomeLoss", "OperatingProfitLoss"]),
                        "assets_history": self._get_sec_metric(facts, ["Assets"]),
                        "liabilities_history": self._get_sec_metric(facts, ["Liabilities"]),
                        "cash_flow_history": self._get_sec_metric(facts, ["NetCashProvidedByUsedInOperatingActivities"]),
                        "shares_outstanding_history": self._get_sec_metric(facts, ["CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding"]),
                        "buybacks_history": self._get_sec_metric(facts, ["PaymentsForRepurchaseOfCommonStock", "PaymentsForRepurchaseOfTreasuryStock", "StockRepurchaseProgramAuthorizedAmount"]),
                        "dividends_history": self._get_sec_metric(facts, ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock", "PaymentsOfDividendsMinorityInterest"]),
                        "capex_history": self._get_sec_metric(facts, ["PaymentsToAcquirePropertyPlantAndEquipment", "CapitalExpenditures", "PaymentsToAcquirePropertyPlantAndEquipmentAndOtherIntangibleAssets"])
                    }
                    
                    for attr, val in data_map.items():
                        if val:
                            evidence_list.append(ResearchEvidence(
                                id=CitationManager.generate_id("sec_data", cik_padded, attr, "current"),
                                entity=cik_padded,
                                attribute=attr,
                                value=val,
                                source="sec_data",
                                source_type="mcp",
                                confidence=0.99
                            ))
                            
        except Exception as e:
            pass
            
        return evidence_list
