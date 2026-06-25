from pydantic import BaseModel
from typing import List, Optional

class EntityExtractionResult(BaseModel):
    company: str
    ticker: Optional[str] = None
    exchange: Optional[str] = None
    cik: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    subindustry: Optional[str] = None
    country: Optional[str] = None
    headquarters: Optional[str] = None

class ResearchTrack(BaseModel):
    agent: str
    objective: str

class PlanningResult(BaseModel):
    intent: str
    workspace_type: str
    companies: List[str]
    research_depth: str
    report_style: str
    required_outputs: List[str]
    research_tracks: List[ResearchTrack]
