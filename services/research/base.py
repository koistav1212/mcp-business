from abc import ABC, abstractmethod
from typing import Any

class BaseProvider(ABC):
    """
    Abstract base class for all data providers in the Business Intelligence Layer.
    Each provider represents a single category of raw facts or events.
    """
    @abstractmethod
    async def fetch(self, company: str) -> Any:
        """
        Fetches raw records and events relating to a target company.
        """
        pass
