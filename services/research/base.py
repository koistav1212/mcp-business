from abc import ABC, abstractmethod
from typing import Any, List, Optional
from services.knowledge.evidence import ResearchEvidence
from services.knowledge.citation_manager import CitationManager

class BaseProvider(ABC):
    """
    Abstract base class for all data providers in the Business Intelligence Layer.
    Each provider represents a single category of raw facts or events.
    """
    
    def _extract_identifier(self, target: Any) -> Optional[str]:
        """
        Safely extracts the ticker or string name from the target object.
        """
        if not target:
            return None
        if isinstance(target, str):
            return target
            
        # If it's a Pydantic model or dict
        if hasattr(target, "ticker") and target.ticker:
            return target.ticker
        if hasattr(target, "company_name") and target.company_name:
            return target.company_name
            
        if isinstance(target, dict):
            return target.get("ticker") or target.get("canonical_name") or target.get("company_name") or str(target)
            
        return str(target)

    @abstractmethod
    async def fetch(self, target: Any) -> List[ResearchEvidence]:
        """
        Fetches records relating to a target company and returns normalized Evidence.
        """
        pass
