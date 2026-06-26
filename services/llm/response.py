from pydantic import BaseModel
from typing import Dict, Any

class LLMResponse(BaseModel):
    content: str
    usage: Dict[str, int]
    provider: str
    model: str
    latency_ms: float
    finish_reason: str
