from abc import ABC, abstractmethod
from services.llm.request import LLMRequest
from services.llm.response import LLMResponse

class BaseProvider(ABC):
    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Execute an LLM request and return a standardized response."""
        pass
