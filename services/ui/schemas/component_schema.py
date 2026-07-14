from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class ComponentSchema(BaseModel):
    id: str
    type: str
    title: str
    span: int = Field(default=12)
    analytical_question: str
    bindings: List[str] = Field(default_factory=list)
    derived_content: Dict[str, Any] = Field(default_factory=dict)
    evidence_paths: List[str] = Field(default_factory=list)
