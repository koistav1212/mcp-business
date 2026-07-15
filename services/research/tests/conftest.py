import pytest
from typing import Any
from unittest.mock import patch
from services.research.tests.fixtures import MOCK_COMPANY_RESPONSES
from services.research.providers.entity_resolver import EntityResolver
from services.research.providers.company_provider import CompanyProvider
from services.research.providers.news.news_provider import NewsProvider
from services.research.providers.yfinance_provider import YFinanceProvider
from services.research.providers.people_provider import PeopleProvider
from services.research.providers.web_provider import WebProvider
from services.research.providers.reddit_provider import RedditProvider
from services.research.synthesizer import ResearchSynthesizer
from services.schemas.insight import SWOTAnalysis
import os

os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434/v1"

@pytest.fixture(autouse=True)
def mock_providers():
    original_get_candidates = EntityResolver.get_candidates
    original_company_fetch = CompanyProvider.fetch
    original_news_fetch = NewsProvider.fetch
    original_yfinance_fetch = YFinanceProvider.fetch
    original_people_fetch = PeopleProvider.fetch
    original_web_fetch = WebProvider.fetch
    original_reddit_fetch = RedditProvider.fetch
    original_synthesize = ResearchSynthesizer.synthesize

    async def mock_get_candidates(self, query: str):
        query_lower = query.lower()
        if "zoho" in query_lower:
            return MOCK_COMPANY_RESPONSES["zoho"]["entity_resolution"]
        elif "google" in query_lower:
            return MOCK_COMPANY_RESPONSES["google"]["entity_resolution"]
        elif "acme" in query_lower:
            return MOCK_COMPANY_RESPONSES["acme"]["entity_resolution"]
        return await original_get_candidates(self, query)

    async def mock_company_fetch(self, company: str):
        company_lower = company.lower()
        if "zoho" in company_lower:
            return MOCK_COMPANY_RESPONSES["zoho"]["company"]
        elif "google" in company_lower:
            return MOCK_COMPANY_RESPONSES["google"]["company"]
        elif "acme" in company_lower:
            return MOCK_COMPANY_RESPONSES["acme"]["company"]
        return await original_company_fetch(self, company)

    async def mock_news_fetch(self, company: str):
        company_lower = company.lower()
        if "zoho" in company_lower:
            return MOCK_COMPANY_RESPONSES["zoho"]["news"]
        elif "google" in company_lower:
            return MOCK_COMPANY_RESPONSES["google"]["news"]
        elif "acme" in company_lower:
            return MOCK_COMPANY_RESPONSES["acme"].get("news", {
                "source_title": "Google News RSS Feed",
                "source_url": f"https://news.google.com/rss/search?q={company_lower}",
                "source_type": "news_outlet",
                "news": [],
                "raw_data": {}
            })
        return await original_news_fetch(self, company)

    async def mock_yfinance_fetch(self, target: Any):
        ticker_symbol = self._extract_identifier(target)
        if not ticker_symbol:
            return await original_yfinance_fetch(self, target)
        ticker_upper = ticker_symbol.upper()
        if "ZOHO" in ticker_upper or "MOCK" in ticker_upper:
            if "ZOHO" in ticker_upper:
                return MOCK_COMPANY_RESPONSES["zoho"]["market"]
            elif "ACME" in ticker_upper:
                return MOCK_COMPANY_RESPONSES["acme"].get("market", {
                    "market_cap": None,
                    "pe_ratio": None,
                    "current_price": None,
                    "fifty_two_week_high": None,
                    "fifty_two_week_low": None,
                    "raw_data": {"note": "No ticker symbol resolved or private company."}
                })
        return await original_yfinance_fetch(self, target)

    async def mock_people_fetch(self, company: str):
        company_lower = company.lower()
        if "zoho" in company_lower:
            return MOCK_COMPANY_RESPONSES["zoho"]["people"]
        elif "google" in company_lower:
            return MOCK_COMPANY_RESPONSES["google"]["people"]
        elif "acme" in company_lower:
            return MOCK_COMPANY_RESPONSES["acme"]["people"]
        return await original_people_fetch(self, company)

    async def mock_web_fetch(self, company: str):
        company_lower = company.lower()
        if "zoho" in company_lower:
            return MOCK_COMPANY_RESPONSES["zoho"]["technology"]
        elif "google" in company_lower:
            return MOCK_COMPANY_RESPONSES["google"]["technology"]
        elif "acme" in company_lower:
            return MOCK_COMPANY_RESPONSES["acme"]["technology"]
        return await original_web_fetch(self, company)

    async def mock_reddit_fetch(self, company: str):
        company_lower = company.lower()
        if "zoho" in company_lower:
            return MOCK_COMPANY_RESPONSES["zoho"]["social"]
        return await original_reddit_fetch(self, company)

    async def mock_synthesize(self, bundle, entity, sec_data, yf_data, reddit_data):
        from services.schemas.insight import ResearchContext, CompanyProfile, SourcedValue, HiringSignal, SWOTAnalysis, FinancialData
        context = ResearchContext()
        context.entity = entity
        
        is_nvidia = entity and entity.company_name and "nvidia" in entity.company_name.lower()
        
        if not is_nvidia:
            context.profile = CompanyProfile(
                name="Zoho Corporation",
                overview="Zoho is a great company.",
                employee_count=SourcedValue(value=12000, source_ids=["mock"]),
                headquarters=SourcedValue(value="Chennai, India & Austin, Texas", source_ids=["mock"])
            )
            # 2. tech stack
            context.technology_stack = [SourcedValue(value="React"), SourcedValue(value="PostgreSQL")]
            # 3. Leadership & Competitors
            context.leadership = [SourcedValue(name="Sridhar Vembu"), SourcedValue(name="Radha Vembu")]
            context.competitors = [SourcedValue(name="Salesforce"), SourcedValue(name="HubSpot")]
            # 4. News
            context.news = [SourcedValue(title="Zoho launches new AI-driven CRM tools")]
            # 5. Hiring Signals
            context.hiring_signals = [HiringSignal(role_title="Senior React Developer")]
            # 6. sources
            context.sources = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
            
            context.swot = SWOTAnalysis(
                strengths=["Robust bootstrapped product ecosystem (Zoho One)", "Cost advantage vs venture-backed peers"],
                weaknesses=["Brand awareness in massive enterprise segments"],
                opportunities=["Expansion of AI-driven workflow engines"],
                threats=["Aggressive enterprise pricing packages from Salesforce"]
            )
            
            context.financials = FinancialData(
                revenue_annual="1B",
                funding_total="0",
                last_round="N/A"
            )
        return context

    with patch.object(EntityResolver, "get_candidates", mock_get_candidates), \
         patch.object(CompanyProvider, "fetch", mock_company_fetch), \
         patch.object(NewsProvider, "fetch", mock_news_fetch), \
         patch.object(YFinanceProvider, "fetch", mock_yfinance_fetch), \
         patch.object(PeopleProvider, "fetch", mock_people_fetch), \
         patch.object(WebProvider, "fetch", mock_web_fetch), \
         patch.object(RedditProvider, "fetch", mock_reddit_fetch), \
         patch.object(ResearchSynthesizer, "synthesize", mock_synthesize):
        yield
