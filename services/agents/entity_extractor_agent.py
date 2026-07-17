import json
import logging
from services.core.models import EntityExtractionResult
from services.llm.provider_router import ProviderRouter
from services.research.providers.entity_resolver import EntityResolver

logger = logging.getLogger("uvicorn.error")

EXTRACTOR_SYSTEM_PROMPT = """You are a Data Extraction Entity.
Extract the company name, industry, and country from the user's research query.

IMPORTANT instructions for company extraction:
- The user's query may begin with verbs or introductory phrases such as: "analyse", "analyze", "research", "study", "evaluate", "investigate", "compare", "tell me about", "look up", "find", "get".
- These action verbs and phrases ARE NOT part of the company name. Strip them and extract only the actual company name (e.g. for "analyse apple", the company name is "Apple").
- Remove any generic punctuation or filler words from the extracted company name.

You MUST respond with a single JSON object and NOTHING else.
Do not include explanations, bullet points, markdown, or thinking.
If you need to think, do it silently; only output the final JSON exactly matching this schema:
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
"""

class EntityExtractorAgent:
    async def execute(self, user_query: str) -> EntityExtractionResult:
        result = None
        if True:
            try:
                payload = await ProviderRouter.generate_json(
                    agent_name="entity_extractor",
                    system_prompt=EXTRACTOR_SYSTEM_PROMPT,
                    user_prompt=json.dumps({"prompt": user_query})
                )
                result = EntityExtractionResult.model_validate(payload)
            except Exception as e:
                logger.warning(f"Entity extractor LLM failed: {e}. Falling back to basic parsing.")
                
        if not result:
            # Basic heuristic fallback
            query = user_query.strip()
            for verb in ["analyze", "analyse", "research", "investigate", "tell me about", "look up", "find", "get", "study", "evaluate", "compare"]:
                if query.lower().startswith(verb):
                    query = query[len(verb):].strip()
            
            # Remove punctuation
            query = query.strip(" .:,;!?")
                    
            result = EntityExtractionResult(
                company=query[:50],
                industry=None,
                country=None,
                ticker=None,
                exchange=None,
                cik=None,
                website=None,
                subindustry=None,
                headquarters=None
            )
            
        # Post-process result.company with heuristic cleanup to remove verbs if LLM output still has them!
        if result.company:
            cleaned_company = result.company.strip()
            for verb in ["analyze", "analyse", "research", "investigate", "tell me about", "look up", "find", "get", "study", "evaluate", "compare"]:
                if cleaned_company.lower().startswith(verb + " "):
                    cleaned_company = cleaned_company[len(verb) + 1:].strip()
                elif cleaned_company.lower().startswith(verb):
                    cleaned_company = cleaned_company[len(verb):].strip()
            cleaned_company = cleaned_company.strip(" .:,;!?")
            if cleaned_company:
                result.company = cleaned_company

        # Use EntityResolver to fill in authoritative ticker, exchange, etc.
        if result.company:
            resolver = EntityResolver()
            candidates = await resolver.get_candidates(result.company)
            if candidates:
                best = candidates[0].entity
                result.company = best.name or result.company
                if not result.ticker:
                    result.ticker = best.ticker
                if not result.exchange:
                    result.exchange = best.exchange
                if not result.cik:
                    result.cik = best.cik
                if not result.industry:
                    result.industry = best.industry
                if not result.subindustry:
                    result.subindustry = best.subindustry
                if not result.country:
                    result.country = best.country
                if not result.website:
                    result.website = best.website
                    
        return result
