from typing import List
from services.knowledge.views.base_view import KnowledgeView
from services.knowledge.evidence_store import EvidenceStore
from services.knowledge.evidence import ResearchEvidence

class CompetitorView(KnowledgeView):
    def build(self, entity: str, evidence_store: EvidenceStore) -> List[ResearchEvidence]:
        all_evidence = evidence_store.get_all_for_entity(entity)
        
        allowed_sources = ["company_profile", "market_data", "news_feed"]
        competitor_evidence = [
            ev for ev in all_evidence 
            if ev.attribute in ["competitors", "pricing", "products", "market_share", "ai_position", "launches", "features", "swot"]
        ]
        
        competitor_evidence.sort(key=lambda x: x.confidence, reverse=True)
        return competitor_evidence
