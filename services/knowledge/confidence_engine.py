from typing import List, Dict
from .evidence import ResearchEvidence
from .source_registry import SourceRegistry

class ConfidenceEngine:
    """
    Scores facts based on corroboration across multiple independent sources.
    """
    @classmethod
    def score_evidence_group(cls, evidence_list: List[ResearchEvidence]) -> float:
        if not evidence_list:
            return 0.0
            
        # Base confidence from the primary (highest confidence) source
        max_confidence = max(ev.confidence for ev in evidence_list)
        
        # Count unique sources that corroborate this fact
        unique_sources = set(ev.source for ev in evidence_list)
        
        # Boost confidence by 0.05 for each corroborating source, up to 0.99
        boost = (len(unique_sources) - 1) * 0.05
        
        final_score = min(0.99, max_confidence + boost)
        return final_score

    @classmethod
    def initialize_confidence(cls, source_name: str, base_confidence: float = 0.5) -> float:
        """
        Get the initial confidence score based on the source registry trust score.
        """
        source_info = SourceRegistry.get_source_info(source_name)
        if source_info:
            return source_info.trust_score
        return base_confidence
