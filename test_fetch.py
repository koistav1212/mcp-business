import asyncio
from services.research.providers.yfinance_provider import YFinanceProvider
from services.research.providers.news_provider import NewsProvider

async def main():
    yf = YFinanceProvider()
    res = await yf.fetch("AAPL")
    print(f"market_data: type={type(res)}, bool={bool(res)}, val={res}")
    
    nf = NewsProvider()
    res2 = await nf.fetch("AAPL")
    print(f"news_feed: type={type(res2)}, bool={bool(res2)}, val={res2}")

asyncio.run(main())
