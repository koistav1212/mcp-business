import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from services.research.base import BaseProvider
from services.knowledge.evidence import ResearchEvidence
from services.research.providers.shared_utils import _BOT_UA, _get, _write_json, _emit, logger

class SECEdgarProvider(BaseProvider):
    """
    Fetches structured financial data from SEC EDGAR XBRL CompanyFacts API.
    """
    _BASE = "https://data.sec.gov"
    _HEADERS = {"User-Agent": _BOT_UA, "Accept-Encoding": "gzip, deflate"}

    _METRICS: Dict[str, List[str]] = {
        "revenue_history": [
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "SalesRevenueNet",
            "SalesRevenueGoodsNet",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
        ],
        "net_income_history": ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
        "operating_income_history": ["OperatingIncomeLoss", "OperatingProfitLoss"],
        "gross_profit_history": ["GrossProfit"],
        "assets_history": ["Assets"],
        "liabilities_history": ["Liabilities"],
        "equity_history": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
        "cash_flow_history": [
            "NetCashProvidedByUsedInOperatingActivities",
            "CashFlowFromOperations",
        ],
        "free_cash_flow_history": ["FreeCashFlow"],
        "shares_outstanding_history": [
            "CommonStockSharesOutstanding",
            "EntityCommonStockSharesOutstanding",
        ],
        "buybacks_history": [
            "PaymentsForRepurchaseOfCommonStock",
            "PaymentsForRepurchaseOfTreasuryStock",
        ],
        "dividends_history": [
            "PaymentsOfDividends",
            "PaymentsOfDividendsCommonStock",
        ],
        "capex_history": [
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "CapitalExpenditures",
        ],
        "rd_expense_history": [
            "ResearchAndDevelopmentExpense",
            "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
        ],
        "interest_expense_history": ["InterestExpense", "InterestExpenseDebt"],
        "long_term_debt_history": ["LongTermDebt", "LongTermDebtAndCapitalLeaseObligations"],
    }

    def _extract_cik(self, target: Any) -> Optional[str]:
        if hasattr(target, "cik") and target.cik:
            return str(target.cik)
        if isinstance(target, dict):
            return str(target.get("cik", ""))
        return str(target) if target else None

    def _get_metric(
        self, facts: Dict, concepts: List[str], form_types: Tuple[str, ...] = ("10-K",)
    ) -> Dict[str, float]:
        merged: Dict[int, Dict] = {}
        for concept in reversed(concepts):
            if concept not in facts:
                continue
            units = facts[concept].get("units", {})
            if not units:
                continue
            unit_key = "USD" if "USD" in units else next(iter(units))
            for entry in units[unit_key]:
                if entry.get("form") not in form_types:
                    continue
                fy = entry.get("fy")
                filed = entry.get("filed", "")
                val = entry.get("val")
                if fy is None or val is None:
                    continue
                if fy not in merged or filed > merged[fy].get("filed", ""):
                    merged[fy] = entry
        sorted_fy = sorted(merged.keys())[-10:]
        return {str(fy): float(merged[fy]["val"]) for fy in sorted_fy}

    async def _fetch_metadata(
        self, client: httpx.AsyncClient, cik_padded: str
    ) -> Dict[str, Any]:
        url = f"{self._BASE}/submissions/CIK{cik_padded}.json"
        r = await _get(client, url, headers=self._HEADERS)
        if not r:
            return {}
        try:
            data = r.json()
            return {
                "sic": data.get("sic"),
                "sic_description": data.get("sicDescription", ""),
                "state_of_inc": data.get("stateOfIncorporation", ""),
                "fiscal_year_end": data.get("fiscalYearEnd", ""),
                "category": data.get("category", ""),
                "entity_type": data.get("entityType", ""),
                "filings_recent": data.get("filings", {}).get("recent", {}),
            }
        except Exception:
            return {}

    async def _fetch_10k_text(
        self,
        client: httpx.AsyncClient,
        cik_padded: str,
        metadata: Dict,
    ) -> Dict[str, str]:
        out: Dict[str, str] = {}
        try:
            recent = metadata.get("filings_recent", {})
            forms = recent.get("form", [])
            accns = recent.get("accessionNumber", [])
            for form, accn in zip(forms, accns):
                if form == "10-K":
                    accn_clean = accn.replace("-", "")
                    index_url = f"{self._BASE}/Archives/edgar/data/{int(cik_padded)}/{accn_clean}/{accn}-index.json"
                    r = await _get(client, index_url, headers=self._HEADERS)
                    if r:
                        files = r.json().get("directory", {}).get("item", [])
                        for f in files:
                            name = f.get("name", "")
                            if name.endswith(".htm") and "10-k" in name.lower():
                                doc_url = f"{self._BASE}/Archives/edgar/data/{int(cik_padded)}/{accn_clean}/{name}"
                                r2 = await _get(client, doc_url, headers=self._HEADERS)
                                if r2:
                                    html = r2.text
                                    plain = re.sub(r"<[^>]+>", " ", html)
                                    plain = re.sub(r"\s+", " ", plain)
                                    rf_match = re.search(
                                        r"(?:RISK FACTORS|Item\s+1A\.?\s+Risk Factors)(.*?)(?:Item\s+1B\.|Item\s+2\.|UNRESOLVED)",
                                        plain, re.IGNORECASE | re.DOTALL,
                                    )
                                    if rf_match:
                                        out["risk_factors_text"] = rf_match.group(1).strip()[:3000]
                                    mda_match = re.search(
                                        r"(?:MANAGEMENT'S DISCUSSION|Item\s+7\.?\s+Management)(.*?)(?:Item\s+7A\.|Item\s+8\.)",
                                        plain, re.IGNORECASE | re.DOTALL,
                                    )
                                    if mda_match:
                                        out["mda_text"] = mda_match.group(1).strip()[:3000]
                                break
                    break
        except Exception as exc:
            logger.debug(f"10-K text extraction failed: {exc}")
        return out

    async def fetch(self, target: Any) -> List[ResearchEvidence]:
        cik = self._extract_cik(target)
        if not cik:
            return []
        cik_str = "".join(filter(str.isdigit, cik.strip()))
        if not cik_str or cik_str in ("0000000000", "0"):
            return []
        cik_padded = cik_str.zfill(10)
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        evidence_list: List[ResearchEvidence] = []

        async with httpx.AsyncClient(headers=self._HEADERS, timeout=15.0) as client:
            facts_url = f"{self._BASE}/api/xbrl/companyfacts/CIK{cik_padded}.json"
            facts_task = _get(client, facts_url, headers=self._HEADERS)
            meta_task = self._fetch_metadata(client, cik_padded)
            r_facts, metadata = await asyncio.gather(facts_task, meta_task)

            if r_facts:
                raw = r_facts.json()
                facts = raw.get("facts", {}).get("us-gaap", {})
                _write_json(f"sec_{cik_padded}.json", {k: "..." for k in facts.keys()})

                entity_name = raw.get("entityName", cik_padded)

                for attr, concepts in self._METRICS.items():
                    history = self._get_metric(facts, concepts, ("10-K",))
                    if not history:
                        history = self._get_metric(facts, concepts, ("10-K", "10-Q"))
                    if history:
                        _emit(
                            evidence_list,
                            entity=cik_padded,
                            attribute=attr,
                            value=history,
                            source="sec_edgar",
                            source_type="mcp",
                            confidence=0.99,
                            now_str=now_str,
                            source_url=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json",
                        )

            if metadata:
                _emit(evidence_list, entity=cik_padded, attribute="sic_code",
                      value=metadata.get("sic"), source="sec_edgar", source_type="mcp",
                      confidence=0.99, now_str=now_str)
                _emit(evidence_list, entity=cik_padded, attribute="sic_description",
                      value=metadata.get("sic_description"), source="sec_edgar", source_type="mcp",
                      confidence=0.99, now_str=now_str)
                _emit(evidence_list, entity=cik_padded, attribute="fiscal_year_end",
                      value=metadata.get("fiscal_year_end"), source="sec_edgar", source_type="mcp",
                      confidence=0.99, now_str=now_str)

                text_data = await self._fetch_10k_text(client, cik_padded, metadata)
                if text_data.get("risk_factors_text"):
                    _emit(evidence_list, entity=cik_padded, attribute="risk_factors_text",
                          value=text_data["risk_factors_text"], source="sec_edgar_10k",
                          source_type="mcp", confidence=0.97, now_str=now_str)
                if text_data.get("mda_text"):
                    _emit(evidence_list, entity=cik_padded, attribute="mda_text",
                          value=text_data["mda_text"], source="sec_edgar_10k",
                          source_type="mcp", confidence=0.97, now_str=now_str)

        _write_json(
            f"sec_evidence_{cik_padded}.json",
            [e.model_dump(mode='json') for e in evidence_list],
        )
        logger.info(f"SECEdgarProvider: {len(evidence_list)} evidence items for CIK {cik_padded}")
        return evidence_list
