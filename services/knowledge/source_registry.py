from pydantic import BaseModel
from typing import Optional

class SourceMetadata(BaseModel):
    source: str
    type: str
    trust_score: float
    freshness: str
    update_frequency: str
    latency: str
    cost: str
    coverage: str
    supports_structured_data: bool
    supports_historical_data: bool
    rate_limit: str
    preferred_agent: str

class SourceRegistry:
    SOURCES = {
        "sec": SourceMetadata(
            source="sec",
            type="financial_filings",
            trust_score=1.0,
            freshness="quarterly",
            update_frequency="quarterly",
            latency="low",
            cost="free",
            coverage="public_equities",
            supports_structured_data=True,
            supports_historical_data=True,
            rate_limit="10_per_sec",
            preferred_agent="financial_agent"
        ),
        "yahoo": SourceMetadata(
            source="yahoo",
            type="market_data",
            trust_score=0.9,
            freshness="realtime",
            update_frequency="realtime",
            latency="low",
            cost="free",
            coverage="global_equities",
            supports_structured_data=True,
            supports_historical_data=True,
            rate_limit="2000_per_hour",
            preferred_agent="market_agent"
        ),
        "news": SourceMetadata(
            source="news",
            type="media",
            trust_score=0.8,
            freshness="daily",
            update_frequency="continuous",
            latency="medium",
            cost="free",
            coverage="global",
            supports_structured_data=False,
            supports_historical_data=True,
            rate_limit="100_per_day",
            preferred_agent="news_agent"
        )
    }

    @classmethod
    def get_source_info(cls, source_name: str) -> Optional[SourceMetadata]:
        return cls.SOURCES.get(source_name.lower())
