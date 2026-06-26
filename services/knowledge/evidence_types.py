from pydantic import Field
from typing import Optional, List, Dict, Any
from .evidence import ResearchEvidence

class FinancialEvidence(ResearchEvidence):
    metric: str
    period: str
    currency: Optional[str] = "USD"
    
class NewsEvidence(ResearchEvidence):
    headline: str
    publisher: str
    published: str
    entities: List[str] = Field(default_factory=list)
    sentiment: str = "neutral"
    category: str = "general"
    importance: str = "medium"
    summary: str
    
class CompanyEvidence(ResearchEvidence):
    ceo: Optional[str] = None
    employees: Optional[int] = None
    market_cap: Optional[float] = None
    products: List[str] = Field(default_factory=list)
    headquarters: Optional[str] = None
    founded: Optional[str] = None
    industry: Optional[str] = None
    exchange: Optional[str] = None
    ticker: Optional[str] = None
    
class PatentEvidence(ResearchEvidence):
    pass
    
class HiringEvidence(ResearchEvidence):
    pass
    
class SocialEvidence(ResearchEvidence):
    pass
    
class ExecutiveEvidence(ResearchEvidence):
    pass
    
class MacroEvidence(ResearchEvidence):
    pass
    
class IndustryEvidence(ResearchEvidence):
    pass
    
class TechnologyEvidence(ResearchEvidence):
    pass
    
class ProductEvidence(ResearchEvidence):
    pass
    
class RiskEvidence(ResearchEvidence):
    pass
