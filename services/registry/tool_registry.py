from services.research.providers.sec_edgar_provider import SECEdgarProvider
from services.research.providers.yfinance_provider import YFinanceProvider
from services.research.providers.news_provider import NewsProvider
from services.research.providers.company_provider import CompanyProvider
from services.research.providers.web_provider import WebProvider
from services.research.providers.people_provider import PeopleProvider
from services.research.providers.reddit_provider import RedditProvider

TOOLS = {
    "company_profile": {
        "mcp_server": "company-mcp",
        "cost": 1,
        "quality": 0.9,
        "instance": CompanyProvider()
    },
    "sec_data": {
        "mcp_server": "sec-mcp",
        "cost": 2,
        "quality": 0.95,
        "instance": SECEdgarProvider()
    },
    "market_data": {
        "mcp_server": "market-mcp",
        "cost": 1,
        "quality": 0.9,
        "instance": YFinanceProvider()
    },
    "news_feed": {
        "mcp_server": "news-mcp",
        "cost": 1,
        "quality": 0.8,
        "instance": NewsProvider()
    },
    "technology_stack": {
        "mcp_server": "web-mcp",
        "cost": 1,
        "quality": 0.85,
        "instance": WebProvider()
    },
    "people_data": {
        "mcp_server": "people-mcp",
        "cost": 3,
        "quality": 0.85,
        "instance": PeopleProvider()
    },
    "social_sentiment": {
        "mcp_server": "social-mcp",
        "cost": 1,
        "quality": 0.7,
        "instance": RedditProvider()
    }
}
