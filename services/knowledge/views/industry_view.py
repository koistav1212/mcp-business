from typing import List
from services.knowledge.views.base_view import KnowledgeView
from services.knowledge.evidence_store import EvidenceStore
from services.knowledge.evidence import ResearchEvidence

class IndustryView(KnowledgeView):
    def build(self, entity: str, evidence_store: EvidenceStore) -> List[ResearchEvidence]:
        all_evidence = evidence_store.get_all_for_entity(entity)
        
        allowed_sources = ["news_feed", "company_profile"]
        industry_evidence = [
            ev for ev in all_evidence 
            if ev.attribute in ["industry", "market", "sector", "tam", "regulations", "trends"]
        ]
        
        industry_evidence.sort(key=lambda x: x.confidence, reverse=True)
        return industry_evidence
