from typing import Any, Dict, List

from pydantic import BaseModel, Field


class SignalProfile(BaseModel):
    available: bool = False
    completeness: float = 0.0
    confidence: float = 0.0
    item_count: int = 0
    evidence_paths: List[str] = Field(default_factory=list)
    signals: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DataProfile(BaseModel):
    entity_identity: SignalProfile = Field(default_factory=SignalProfile)
    company_scale: SignalProfile = Field(default_factory=SignalProfile)
    business_architecture: SignalProfile = Field(default_factory=SignalProfile)
    platform_structure: SignalProfile = Field(default_factory=SignalProfile)
    brand_portfolio: SignalProfile = Field(default_factory=SignalProfile)
    geographic_footprint: SignalProfile = Field(default_factory=SignalProfile)
    financial_history: SignalProfile = Field(default_factory=SignalProfile)
    news_intelligence: SignalProfile = Field(default_factory=SignalProfile)
    leadership: SignalProfile = Field(default_factory=SignalProfile)
    social_intelligence: SignalProfile = Field(default_factory=SignalProfile)
