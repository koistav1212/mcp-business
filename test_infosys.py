import asyncio
from services.research.providers.entity_resolver import EntityResolver

async def main():
    resolver = EntityResolver()
    candidates = await resolver.get_candidates("Infosys")
    for c in candidates:
         print(f"Name: {c.company_name}, Ticker: {c.ticker}, Exchange: {c.exchange}")

if __name__ == "__main__":
    asyncio.run(main())
