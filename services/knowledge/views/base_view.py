from abc import ABC, abstractmethod
from typing import List
from services.knowledge.evidence_store import EvidenceStore
from services.knowledge.evidence import ResearchEvidence

class KnowledgeView(ABC):
    """
    Base class for domain-specific Knowledge Views.
    Each view is responsible for filtering the EvidenceStore down to 
    only the subset of evidence relevant to its domain.
    """
    
    @abstractmethod
    def build(self, entity: str, evidence_store: EvidenceStore) -> List[ResearchEvidence]:
        raise NotImplementedError
