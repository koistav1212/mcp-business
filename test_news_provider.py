import asyncio
from services.research.providers.news.news_provider import NewsProvider

class DummyTarget:
    ticker = "AAPL"
    
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name

async def main():
    print("Initializing NewsProvider...")
    provider = NewsProvider()
    print("Fetching news for Apple...")
    results = await provider.fetch(DummyTarget("Apple"))
    print(f"Got {len(results)} finalized evidence items.")
    for r in results[:2]:
        print(f"- {r.value.get('headline')} (Score: {r.value.get('importance')})")

if __name__ == "__main__":
    asyncio.run(main())
