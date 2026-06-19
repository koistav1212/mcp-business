from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, Field

class Source(BaseModel):
    """
    Represents a citation source for verifiability and audits.
    """
    title: str
    url: str
    source_type: str
    published_at: Optional[datetime] = None

class CompanyProfile(BaseModel):
    name: str
    overview: str
    headquarters: str
    employee_count: int
    website: str

class LeadershipMember(BaseModel):
    name: str
    role: str
    linkedin_url: Optional[str] = None

class Competitor(BaseModel):
    name: str
    website: str
    segment: str

class FinancialInfo(BaseModel):
    revenue_annual: str
    funding_total: str
    last_round: str

class NewsItem(BaseModel):
    title: str
    url: str
    date: Optional[str] = None
    snippet: str
    type: str  # general, funding, acquisition, partnership

class HiringSignal(BaseModel):
    role_title: str
    department: str
    location: str

class RawResearchBundle(BaseModel):
    """
    Intermediate bundle wrapping the raw inputs of all providers.
    Passed directly to the synthesizer for resolution and scoring.
    """
    company_raw: Any
    web_raw: Any
    news_raw: Any
    financial_raw: Any
    people_raw: Any

class ResearchContext(BaseModel):
    """
    Unified result object aggregating all normalized research intelligence.
    """
    company_profile: CompanyProfile
    leadership: List[LeadershipMember] = Field(default_factory=list)
    competitors: List[Competitor] = Field(default_factory=list)
    financials: Optional[FinancialInfo] = None
    news: List[NewsItem] = Field(default_factory=list)
    hiring_signals: List[HiringSignal] = Field(default_factory=list)
    technology_stack: List[str] = Field(default_factory=list)
    sources: List[Source] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    generated_at: datetime = Field(default_factory=datetime.utcnow)
