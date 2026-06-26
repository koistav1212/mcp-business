from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

class ResearchEvidence(BaseModel):
    """
    Base object representing a single normalized, structured fact 
    retrieved from any data source (MCP).
    """
    id: str
    entity: str
    attribute: str
    value: Any
    source: str
    source_url: Optional[str] = None
    source_type: str
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    confidence: float = 0.5
    freshness: str = "current"
    tags: List[str] = Field(default_factory=list)
    raw_payload: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra='allow')
