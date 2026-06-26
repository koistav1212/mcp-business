from typing import List
from services.knowledge.views.base_view import KnowledgeView
from services.knowledge.evidence_store import EvidenceStore
from services.knowledge.evidence import ResearchEvidence

class TechnologyView(KnowledgeView):
    def build(self, entity: str, evidence_store: EvidenceStore) -> List[ResearchEvidence]:
        all_evidence = evidence_store.get_all_for_entity(entity)
        
        allowed_sources = ["technology_stack", "company_profile"]
        tech_evidence = [
            ev for ev in all_evidence 
            if ev.source in allowed_sources or ev.attribute in ["technology", "patents", "github", "hiring", "ai_models", "cloud", "infrastructure"]
        ]
        
        tech_evidence.sort(key=lambda x: x.confidence, reverse=True)
        return tech_evidence
