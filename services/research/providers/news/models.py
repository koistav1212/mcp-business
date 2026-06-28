from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime

class NewsEvidence(BaseModel):
    headline: str
    summary: str = ""
    full_text: str = ""
    url: str
    publisher: str = "Unknown"
    published_at: Optional[datetime] = None
    
    ticker: str = ""
    company: str = ""
    industry: str = ""
    
    topics: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    
    # Entity Extraction
    entities: List[str] = Field(default_factory=list)
    people: List[str] = Field(default_factory=list)
    organizations: List[str] = Field(default_factory=list)
    products: List[str] = Field(default_factory=list)
    countries: List[str] = Field(default_factory=list)
    
    # Business Signals
    signal_type: List[str] = Field(default_factory=list)
    
    # Clustering & Timeline
    event_cluster: str = ""
    timeline_position: int = 0
    
    # Scoring
    source_score: float = 0.5
    semantic_score: float = 0.0
    importance: float = 0.5
    sentiment: float = 0.0
    confidence: float = 0.8
    
    citation_ids: List[str] = Field(default_factory=list)
    embedding: List[float] = Field(default_factory=list)
    
class EventCluster(BaseModel):
    event_name: str
    event_summary: str
    event_date: Optional[datetime] = None
    supporting_articles: List[NewsEvidence] = Field(default_factory=list)
