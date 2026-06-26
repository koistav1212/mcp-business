import json
import logging
from services.models.planning_models import EntityExtractionResult
from services.llm.provider_router import ProviderRouter

logger = logging.getLogger("uvicorn.error")

EXTRACTOR_SYSTEM_PROMPT = """You are a Data Extraction Entity.
Extract the company name, industry, and country from the user's research query.

Analyze the query and output a JSON object exactly matching this schema:
{
  "company": "string (The core company name to research)",
  "ticker": "string (The stock ticker, if public)",
  "exchange": "string (The stock exchange, if public)",
  "cik": "string (The SEC CIK number, if applicable)",
  "website": "string (The company's primary website)",
  "industry": "string (The industry they operate in)",
  "subindustry": "string (The sub-industry they operate in)",
  "country": "string (The primary country, default to US if unknown)",
  "headquarters": "string (The city/state of headquarters)"
}

Return ONLY the raw JSON object. Do not include markdown formatting.
"""

class EntityExtractorAgent:
    async def execute(self, user_query: str) -> EntityExtractionResult:
        if True:
            try:
                payload = await ProviderRouter.generate_json(
                    agent_name="entity_extractor",
                    system_prompt=EXTRACTOR_SYSTEM_PROMPT,
                    user_prompt=json.dumps({"prompt": user_query})
                )
                return EntityExtractionResult.model_validate(payload)
            except Exception as e:
                logger.warning(f"Entity extractor LLM failed: {e}. Falling back to basic parsing.")
                
        # Basic heuristic fallback
        return EntityExtractionResult(
            company=user_query.strip()[:50],
            industry="Technology",
            country="US",
            ticker=None,
            exchange=None,
            cik=None,
            website=None,
            subindustry=None,
            headquarters=None
        )
