import asyncio
import json
from dotenv import load_dotenv
load_dotenv()
from services.research.providers.web_provider import WebProvider

async def run_test():
    provider = WebProvider()
    
    # We will pass a string representing Walmart
    target = "Walmart"
    
    print("Testing WebProvider on Walmart...")
    evidence_list = await provider.fetch(target)
    
    if evidence_list:
        print("\n=== EXTRACTED DATA ===")
        # We know evidence_list[0] contains the extracted intelligence
        evidence_json = evidence_list[0].value
        print(json.dumps(evidence_json, indent=2))
    else:
        print("\nNo evidence extracted.")

if __name__ == "__main__":
    asyncio.run(run_test())
