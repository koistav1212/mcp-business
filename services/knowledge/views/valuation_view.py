from typing import List
from services.knowledge.views.base_view import KnowledgeView
from services.knowledge.evidence_store import EvidenceStore
from services.knowledge.evidence import ResearchEvidence

class ValuationView(KnowledgeView):
    def build(self, entity: str, evidence_store: EvidenceStore) -> List[ResearchEvidence]:
        all_evidence = evidence_store.get_all_for_entity(entity)
        
        allowed_sources = ["market_data", "financial_data"]
        valuation_evidence = [
            ev for ev in all_evidence 
            if ev.attribute in ["valuation", "market_cap", "pe_ratio", "multiples", "stock_price"]
        ]
        
        valuation_evidence.sort(key=lambda x: x.confidence, reverse=True)
        return valuation_evidence
