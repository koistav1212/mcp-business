from typing import List, Dict, Any
from .evidence import ResearchEvidence
import logging

logger = logging.getLogger("uvicorn.error")

class EvidenceValidator:
    """
    Detects conflicting or inconsistent facts among multiple pieces of evidence.
    """
    @classmethod
    def validate_group(cls, evidence_list: List[ResearchEvidence]) -> Dict[str, Any]:
        """
        Returns a dict indicating if there are conflicts and what they are.
        For simplicity, this compares string representations of values.
        In a real system, numerical variance checks would be needed.
        """
        if not evidence_list or len(evidence_list) == 1:
            return {"has_conflict": False, "conflicts": []}
            
        # Group by stringified value
        value_groups = {}
        for ev in evidence_list:
            val_str = str(ev.value).strip().lower()
            if val_str not in value_groups:
                value_groups[val_str] = []
            value_groups[val_str].append(ev)
            
        if len(value_groups) > 1:
            logger.warning(f"Conflict detected for attribute {evidence_list[0].attribute} among {len(evidence_list)} sources")
            # Collect the varying values
            conflicts = []
            for val_str, evs in value_groups.items():
                sources = [ev.source for ev in evs]
                conflicts.append({"value": evs[0].value, "sources": sources})
            return {"has_conflict": True, "conflicts": conflicts}
            
        return {"has_conflict": False, "conflicts": []}
