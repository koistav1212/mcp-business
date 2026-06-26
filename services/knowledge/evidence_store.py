from typing import List, Dict, Optional, Any
from .evidence import ResearchEvidence
import logging

logger = logging.getLogger("uvicorn.error")

class EvidenceStore:
    """
    Central in-memory store that indexes evidence by entity, topic, and source.
    """
    def __init__(self):
        # Index by entity canonical ID -> topic/attribute -> List[ResearchEvidence]
        self._store: Dict[str, Dict[str, List[ResearchEvidence]]] = {}
        # Global lookup by ID
        self._id_index: Dict[str, ResearchEvidence] = {}

    def add_evidence(self, evidence: ResearchEvidence):
        if not evidence.entity:
            return
            
        entity = evidence.entity
        attribute = evidence.attribute
        
        if entity not in self._store:
            self._store[entity] = {}
            
        if attribute not in self._store[entity]:
            self._store[entity][attribute] = []
            
        self._store[entity][attribute].append(evidence)
        self._id_index[evidence.id] = evidence
        logger.debug(f"Stored evidence {evidence.id} for {entity} -> {attribute}")

    def get_evidence(self, entity: str, attribute: str) -> List[ResearchEvidence]:
        return self._store.get(entity, {}).get(attribute, [])
        
    def get_all_for_entity(self, entity: str) -> List[ResearchEvidence]:
        all_evidence = []
        for attr, evidence_list in self._store.get(entity, {}).items():
            all_evidence.extend(evidence_list)
        return all_evidence

    def get_by_id(self, evidence_id: str) -> Optional[ResearchEvidence]:
        return self._id_index.get(evidence_id)
