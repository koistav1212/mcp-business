from services.research.providers.sec_edgar_provider import SECEdgarProvider
from services.research.providers.yfinance_provider import YFinanceProvider
from services.research.providers.news.news_provider import NewsProvider
from services.research.providers.company_provider import CompanyProvider
from services.research.providers.web_provider import WebProvider
from services.research.providers.people_provider import PeopleProvider
from services.research.providers.reddit_provider import RedditProvider
from services.research.providers.global_markets_provider import GlobalMarketsProvider

TOOLS = {
    "company_provider": {
        "mcp_server": "company-mcp",
        "cost": 1,
        "quality": 0.9,
        "instance": CompanyProvider()
    },
    "sec_edgar": {
        "mcp_server": "sec-mcp",
        "cost": 2,
        "quality": 0.95,
        "instance": SECEdgarProvider()
    },
    "yfinance": {
        "mcp_server": "market-mcp",
        "cost": 1,
        "quality": 0.9,
        "instance": YFinanceProvider()
    },
    "global_markets": {
        "mcp_server": "market-mcp",
        "cost": 2,
        "quality": 0.9,
        "instance": GlobalMarketsProvider()
    },
    "news_provider": {
        "mcp_server": "news-mcp",
        "cost": 1,
        "quality": 0.8,
        "instance": NewsProvider()
    },
    "web_provider": {
        "mcp_server": "web-mcp",
        "cost": 1,
        "quality": 0.85,
        "instance": WebProvider()
    },
    "people_provider": {
        "mcp_server": "people-mcp",
        "cost": 3,
        "quality": 0.85,
        "instance": PeopleProvider()
    },
    "reddit_provider": {
        "mcp_server": "social-mcp",
        "cost": 1,
        "quality": 0.7,
        "instance": RedditProvider()
    }
}
