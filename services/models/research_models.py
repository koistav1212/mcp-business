from pydantic import BaseModel, Field, ConfigDict
from typing import List

class ResearchTrack(BaseModel):
    agent: str
    objective: str

class ResearchMission(BaseModel):
    agents: List[str]
    tracks: List[ResearchTrack]
    iterations: int
    minimum_sources: int

from pydantic import ConfigDict

class AgentResult(BaseModel):
    findings: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    confidence: float = 0.5
    
    model_config = ConfigDict(extra='allow')
