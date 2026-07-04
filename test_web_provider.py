import asyncio
import logging
logging.basicConfig(level=logging.INFO)
import sys
logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)

from services.research.providers.web_provider import WebProvider

async def main():
    provider = WebProvider()
    class Target:
        ticker = "INFY"
        company = "Infosys"
    results = await provider.fetch(Target())
    print("Results:")
    for r in results:
        print(r.model_dump_json(indent=2))

asyncio.run(main())
