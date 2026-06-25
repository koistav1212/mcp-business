import asyncio
from services.research.providers.sec_edgar_provider import SECEdgarProvider
from services.research.providers.yfinance_provider import YFinanceProvider
from services.research.providers.news_provider import NewsProvider
from services.research.providers.company_provider import CompanyProvider
from services.research.providers.web_provider import WebProvider
from services.research.providers.people_provider import PeopleProvider
from services.research.providers.reddit_provider import RedditProvider

class ProviderExecutor:
    def __init__(self):
        self.sec_provider = SECEdgarProvider()
        self.yfinance_provider = YFinanceProvider()
        self.news_provider = NewsProvider()
        self.company_provider = CompanyProvider()
        self.web_provider = WebProvider()
        self.people_provider = PeopleProvider()
        self.reddit_provider = RedditProvider()

    async def execute(self, candidate, providers):
        provider_calls = {
            "sec_provider": lambda: self.sec_provider.fetch(candidate.cik),
            "market_provider": lambda: self.yfinance_provider.fetch(candidate.ticker),
            "news_provider": lambda: self.news_provider.fetch(candidate.company_name),
            "company_provider": lambda: self.company_provider.fetch(candidate.company_name),
            "technology_provider": lambda: self.web_provider.fetch(candidate.company_name),
            "people_provider": lambda: self.people_provider.fetch(candidate.company_name),
            "social_provider": lambda: self.reddit_provider.fetch(candidate.company_name),
        }
        
        selected = [name for name in providers if name in provider_calls]
        tasks = [provider_calls[name]() for name in selected]
        
        results = await asyncio.gather(*tasks)
        
        return dict(zip(selected, results))
