import asyncio
from services.research.providers.entity_resolver import EntityResolver

async def main():
    resolver = EntityResolver()
    res = await resolver.get_candidates("Nvidia")
    for r in res:
        print(f"Name: {r.entity.name}, Ticker: {r.entity.ticker}, Exchange: {r.entity.exchange}, Confidence: {r.metadata.get('confidence')}")
        print(f"  Industry: {r.entity.industry}, Subindustry: {r.entity.subindustry}")

if __name__ == "__main__":
    asyncio.run(main())
