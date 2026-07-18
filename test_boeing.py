import asyncio
import json
import logging
from services.research.providers.competitor_provider import CompetitorProvider
from services.research.providers.operations_provider import OperationsProvider
from services.agents.section_generators.competitor_section_generator import CompetitorSectionGenerator
from services.agents.section_generators.operations_section_generator import OperationsSectionGenerator

# Set up logging to stdout
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn.error")

async def test_providers_and_generators():
    company = "Boeing"
    
    print("=== Testing CompetitorProvider ===")
    competitor_provider = CompetitorProvider()
    competitor_evidence = await competitor_provider.fetch(company)
    print(f"CompetitorProvider returned {len(competitor_evidence)} items.")
    
    print("\n=== Testing OperationsProvider ===")
    operations_provider = OperationsProvider()
    operations_evidence = await operations_provider.fetch(company)
    print(f"OperationsProvider returned {len(operations_evidence)} items.")
    
    print("\n=== Testing LLM Agents ===")
    
    # We construct a mock evidence graph slice as expected by SectionGenerators
    comp_input = {
        "recent_events": [],
        "evidence": [e.model_dump() for e in competitor_evidence]
    }
    
    comp_gen = CompetitorSectionGenerator()
    print("Running CompetitorSectionGenerator...")
    comp_output = await comp_gen.generate(comp_input, company)
    print("Competitor Output:", json.dumps(comp_output.model_dump(), indent=2))
    
    op_input = {
        "recent_events": [],
        "evidence": [e.model_dump() for e in operations_evidence]
    }
    
    op_gen = OperationsSectionGenerator()
    print("Running OperationsSectionGenerator...")
    op_output = await op_gen.generate(op_input, company)
    print("Operations Output:", json.dumps(op_output.model_dump(), indent=2))

if __name__ == "__main__":
    asyncio.run(test_providers_and_generators())
