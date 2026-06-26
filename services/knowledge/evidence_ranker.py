from typing import List
from .evidence import ResearchEvidence

class EvidenceRanker:
    """
    Ranks available evidence by confidence and freshness before passing to Synthesizer.
    """
    @classmethod
    def rank(cls, evidence_list: List[ResearchEvidence]) -> List[ResearchEvidence]:
        if not evidence_list:
            return []
            
        # Simple ranking: higher confidence first. 
        # In the future, this can parse the 'freshness' string (e.g. date) 
        # to boost newer evidence.
        return sorted(evidence_list, key=lambda x: x.confidence, reverse=True)
