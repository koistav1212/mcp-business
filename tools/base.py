from abc import ABC, abstractmethod
from typing import Any, Optional, Type
from pydantic import BaseModel, ConfigDict
from connectors.base import BaseConnector

class BaseTool(BaseModel, ABC):
    """
    Abstract base class for all tools in the AI Agent Framework.
    Subclasses must implement the async execute method.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    args_schema: Optional[Type[BaseModel]] = None
    connector: Optional[BaseConnector] = None

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """
        Execute the tool's primary logic with inputs validated by args_schema.
        """
        pass
