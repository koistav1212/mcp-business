import asyncio
from services.research.models import RawResearchBundle, ResearchContext
from services.research.synthesizer import ResearchSynthesizer

# Import Providers
from services.research.providers.company_provider import CompanyProvider
from services.research.providers.web_provider import WebProvider
from services.research.providers.news_provider import NewsProvider
from services.research.providers.financial_provider import FinancialProvider
from services.research.providers.people_provider import PeopleProvider

class ResearchOrchestrator:
    """
    Central coordinator for the Business Intelligence Layer.
    Orchestrates concurrent provider lookups and coordinates data consolidation.
    """
    def __init__(self):
        self.company_provider = CompanyProvider()
        self.web_provider = WebProvider()
        self.news_provider = NewsProvider()
        self.financial_provider = FinancialProvider()
        self.people_provider = PeopleProvider()
        self.synthesizer = ResearchSynthesizer()

    async def run(self, company: str) -> ResearchContext:
        """
        Executes all data provider fetch routines concurrently,
        bundles the output, and synthesizes it into a unified ResearchContext.
        """
        # Trigger all provider tasks concurrently
        results = await asyncio.gather(
            self.company_provider.fetch(company),
            self.web_provider.fetch(company),
            self.news_provider.fetch(company),
            self.financial_provider.fetch(company),
            self.people_provider.fetch(company)
        )

        # Build raw research bundle
        bundle = RawResearchBundle(
            company_raw=results[0],
            web_raw=results[1],
            news_raw=results[2],
            financial_raw=results[3],
            people_raw=results[4]
        )

        # Synthesize into clean structured ResearchContext
        context = await self.synthesizer.synthesize(bundle)
        return context
