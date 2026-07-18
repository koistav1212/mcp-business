import asyncio
from crawl4ai import AsyncWebCrawler

async def test_search():
    async with AsyncWebCrawler() as crawler:
        print("Testing Yahoo Search...")
        res = await crawler.arun(url="https://search.yahoo.com/search?p=Boeing+competitors")
        print("Yahoo length:", len(res.markdown) if res else 0)
        print("Yahoo preview:", (res.markdown[:200] if res else ""))
        
        print("\nTesting Bing Search...")
        res = await crawler.arun(url="https://www.bing.com/search?q=Boeing+competitors")
        print("Bing length:", len(res.markdown) if res else 0)
        print("Bing preview:", (res.markdown[:200] if res else ""))

if __name__ == "__main__":
    asyncio.run(test_search())
