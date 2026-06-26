from typing import List
from services.knowledge.views.base_view import KnowledgeView
from services.knowledge.evidence_store import EvidenceStore
from services.knowledge.evidence import ResearchEvidence

class NewsView(KnowledgeView):
    def build(self, entity: str, evidence_store: EvidenceStore) -> List[ResearchEvidence]:
        all_evidence = evidence_store.get_all_for_entity(entity)
        
        # Filter for news-related evidence
        allowed_sources = ["news_feed", "social_sentiment"]
        news_evidence = [
            ev for ev in all_evidence 
            if ev.source in allowed_sources or ev.attribute in ["news", "sentiment"]
        ]
        
        # Sort by freshness if available
        news_evidence.sort(key=lambda x: str(x.freshness), reverse=True)
        
        # Latest 25 News
        return news_evidence[:25]
