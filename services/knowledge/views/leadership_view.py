from typing import List
from services.knowledge.views.base_view import KnowledgeView
from services.knowledge.evidence_store import EvidenceStore
from services.knowledge.evidence import ResearchEvidence

class LeadershipView(KnowledgeView):
    def build(self, entity: str, evidence_store: EvidenceStore) -> List[ResearchEvidence]:
        all_evidence = evidence_store.get_all_for_entity(entity)
        
        allowed_sources = ["company_profile", "people_data", "news_feed"]
        leadership_evidence = [
            ev for ev in all_evidence 
            if ev.attribute in ["leadership", "management", "board", "founders", "executives", "ceo"]
        ]
        
        leadership_evidence.sort(key=lambda x: x.confidence, reverse=True)
        return leadership_evidence
