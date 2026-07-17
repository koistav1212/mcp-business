from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class LLMRequest(BaseModel):
    system_prompt: str
    user_prompt: str
    messages: List[Dict[str, str]] = Field(default_factory=list)
    model: str
    temperature: float = 0.0
    max_tokens: Optional[int] = None
    response_format: Optional[Dict] = None
