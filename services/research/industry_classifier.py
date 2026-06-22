import json
import logging
from typing import Optional, Callable, Awaitable, Dict, Any

from services.research.models import IndustryContext, IntentPlan, CompanyProfile
from services.research.json_llm import configured_json_generator

logger = logging.getLogger("uvicorn.error")

CLASSIFIER_SYSTEM_PROMPT = """You are an Industry Classification Agent.
Your task is to correctly identify the primary industry and sub-industry of a given company.
You will be provided with the user's intent, the company profile, official website data, and SEC filing data.

You MUST determine the industry using the following strict priority order:
1. SEC SIC code (from sec_data, if available)
2. Official Website description (from website_data)
3. Annual Report summary (from sec_data or website_data)
4. Company Description (from company_profile)
5. LLM general knowledge fallback (if all else fails)

Output a JSON object containing:
1. "industry": The primary industry (e.g., "automotive", "software", "banking").
2. "sub_industry": The sub-industry (e.g., "passenger vehicles", "SaaS", "retail banking").
3. "confidence": A float between 0.0 and 1.0 indicating your confidence.
4. "key_metrics": A list of strings representing key performance metrics for this industry.
5. "strategic_themes": A list of strings representing current strategic themes for this industry.

Return ONLY the raw JSON object. Do not include markdown code block formatting (like ```json ... ```).
"""

class IndustryClassifier:
    """Classifies the industry of a target company using an LLM and multiple data sources."""

    def __init__(self, json_generator: Optional[Callable[[str, str], Awaitable[Dict[str, Any]]]] = None):
        self.json_generator = json_generator or configured_json_generator()

    async def classify(
        self,
        intent: IntentPlan,
        company_profile: Optional[CompanyProfile] = None,
        website_data: Any = None,
        sec_data: Any = None
    ) -> IndustryContext:
        fallback = IndustryContext(
            industry="general",
            sub_industry=None,
            confidence=0.55,
            key_metrics=["growth", "profitability", "competitive position", "execution risk"],
            strategic_themes=["market position", "operating performance", "risk"]
        )

        if not self.json_generator:
            return fallback

        # Prepare payload (trim fields slightly to avoid massive tokens)
        sec_data_summary = None
        if sec_data:
            sec_data_summary = {
                "sic": sec_data.get("sic"),
                "sic_description": sec_data.get("sic_description"),
                "business_description": sec_data.get("raw_data", {}).get("description")
            }
            
        web_data_summary = None
        if website_data:
            web_data_summary = {
                "technology_stack": website_data.get("technology_stack", []),
                "summary": website_data.get("raw_data", {}).get("summary")
            }

        payload_data = {
            "intent": {
                "primary_goal": intent.primary_goal,
                "industry_focus": intent.industry_focus
            },
            "company_profile": company_profile.model_dump() if company_profile else None,
            "website_data": web_data_summary,
            "sec_data": sec_data_summary
        }

        try:
            payload = await self.json_generator(
                CLASSIFIER_SYSTEM_PROMPT,
                json.dumps(payload_data)
            )
            
            return IndustryContext(
                industry=payload.get("industry", "general"),
                sub_industry=payload.get("sub_industry"),
                confidence=payload.get("confidence", 0.55),
                key_metrics=payload.get("key_metrics", fallback.key_metrics),
                strategic_themes=payload.get("strategic_themes", fallback.strategic_themes)
            )
        except Exception as e:
            logger.warning(f"IndustryClassifier LLM classification failed: {e}. Using fallback.")
            return fallback
