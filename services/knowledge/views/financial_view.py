from typing import List
from services.knowledge.views.base_view import KnowledgeView
from services.knowledge.evidence_store import EvidenceStore
from services.knowledge.evidence import ResearchEvidence

class FinancialView(KnowledgeView):
    def build(self, entity: str, evidence_store: EvidenceStore) -> List[ResearchEvidence]:
        all_evidence = evidence_store.get_all_for_entity(entity)
        
        # Filter for financial-related evidence
        allowed_sources = ["sec_data", "market_data", "financial_data"]
        financial_evidence = [
            ev for ev in all_evidence 
            if ev.source in allowed_sources or ev.attribute in ["revenue", "margin", "market_cap", "financials"]
        ]
        
        # Sort by confidence and freshness if applicable (mock sorting for now)
        financial_evidence.sort(key=lambda x: x.confidence, reverse=True)
        
        return financial_evidence
