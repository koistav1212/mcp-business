from abc import ABC, abstractmethod
from typing import Any, Dict
from pydantic import BaseModel, ConfigDict, Field

class BaseConnector(BaseModel, ABC):
    """
    Abstract base class representing a connection/client to an external API/platform.
    Connectors handle authentication, configuration, rate limiting, and client lifecycle.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    config: Dict[str, Any] = Field(default_factory=dict)

    @abstractmethod
    async def connect(self) -> Any:
        """
        Initialize and authenticate the underlying client connection.
        Returns the active client instance.
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """
        Gracefully close the underlying connection or session.
        """
        pass
