import json
import logging
from typing import Optional, Callable, Awaitable, Dict, Any

from services.research.models import IntentPlan, ResearchPlan
from services.llm.provider_router import ProviderRouter

logger = logging.getLogger("uvicorn.error")

DIRECTOR_SYSTEM_PROMPT = """You are the Research Director Agent for a Business Intelligence platform.
Your task is to analyze the user's intent and output a comprehensive research plan.

Output a JSON object containing:
1. "research_depth": The depth of research required ("shallow", "standard", "deep").
2. "required_sources": A list of source providers. Choose from:
   - "company" (official website/profile)
   - "news" (news articles)
   - "sec" (SEC Edgar filings)
   - "market" (YFinance data)
   - "people" (LinkedIn/hiring data)
   - "technology" (web/tech stack data)
   - "social" (Reddit/social sentiment)
3. "research_questions": A list of specific research questions to answer.
4. "research_iterations": Number of search/synthesis loops (integer between 1 and 10).
5. "minimum_sources": Minimum number of total sources to require (integer between 5 and 50).

Return ONLY the raw JSON object. Do not include markdown code block formatting (like ```json ... ```).
"""

class ResearchDirectorAgent:
    """Dynamically plans the research strategy and specifies required provider configurations."""

    async def plan(self, intent: IntentPlan) -> ResearchPlan:
        # Fallback plan in case of LLM failure
        fallback_plan = {
            "research_depth": "standard",
            "required_sources": ["company", "news"],
            "research_questions": [f"What evidence supports the intent: {intent.decision_type}?"],
            "research_iterations": 5,
            "minimum_sources": 50
        }

        if True:
            try:
                payload = await ProviderRouter.generate_json(
                    agent_name="director",
                    system_prompt=DIRECTOR_SYSTEM_PROMPT,
                    user_prompt=json.dumps({
                        "primary_goal": intent.primary_goal,
                        "decision_type": intent.decision_type,
                        "workspace_type": intent.workspace_type
                    })
                )
                
                # Merge fallback with payload to handle missing fields
                fallback_plan.update(payload)
            except Exception as e:
                logger.warning(f"ResearchDirectorAgent LLM planning failed: {e}. Using fallback.")

        # Map task providers to actual orchestrator provider names
        provider_map = {
            "company": "company_provider",
            "people": "people_provider",
            "technology": "technology_provider",
            "sec": "sec_provider",
            "market": "market_provider",
            "news": "news_provider",
            "social": "social_provider",
            # accept alternate names
            "yfinance": "market_provider",
            "reddit": "social_provider",
            "web": "technology_provider"
        }
        
        selected_sources = fallback_plan.get("required_sources", [])
        
        providers = []
        rationale = {}
        for short_p in selected_sources:
            full_p = provider_map.get(short_p.lower())
            if full_p:
                providers.append(full_p)
                rationale[full_p] = f"dynamically selected for depth: {fallback_plan.get('research_depth')}"

        # ensure default company and news provider are present if not already
        if "company_provider" not in providers:
            providers.insert(0, "company_provider")
            rationale["company_provider"] = "fallback resolve the target profile"
        if "news_provider" not in providers:
            providers.append("news_provider")
            rationale["news_provider"] = "fallback recent developments"
            
        provider_order = [
            "company_provider", "news_provider", "sec_provider", "market_provider",
            "people_provider", "technology_provider", "social_provider",
        ]
        unique_providers = list(dict.fromkeys(providers))

        return ResearchPlan(
            research_depth=fallback_plan.get("research_depth", "standard"),
            research_iterations=fallback_plan.get("research_iterations", 5),
            minimum_sources=fallback_plan.get("minimum_sources", 50),
            providers=[p for p in provider_order if p in unique_providers],
            research_questions=fallback_plan.get("research_questions", []),
            calculations=intent.required_calculations,
            rationale=rationale,
        )
