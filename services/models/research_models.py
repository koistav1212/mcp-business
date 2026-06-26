from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional

class Finding(BaseModel):
    id: str = Field(description="Unique identifier for this finding (e.g. FINDING-001)")
    description: str = Field(description="The actual insight or synthesized fact")
    evidence_refs: List[str] = Field(default_factory=list, description="List of evidence IDs that support this finding")
    confidence: float = Field(default=0.5, description="Confidence score for this finding")
    
class ResearchTrack(BaseModel):
    agent: str
    objective: str

class ResearchMission(BaseModel):
    agents: List[str]
    tracks: List[ResearchTrack]
    iterations: int
    minimum_sources: int

class AgentResult(BaseModel):
    findings: List[Finding] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    confidence: float = 0.5
    
    model_config = ConfigDict(extra='allow')
