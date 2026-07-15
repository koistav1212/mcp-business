import json
import logging
from typing import Dict, Any, List
import httpx
from services.llm.provider_router import ProviderRouter
from core.config import settings

logger = logging.getLogger("uvicorn.error")

class CrossProviderReasoningAgent:
    """
    Consumes all generated sections (Financials, Competitors, Technology, News, etc.)
    and correlates them to generate validated executive signals.
    """
    async def execute(self, sections: Dict[str, Any], entity_name: str) -> List[str]:
        if not sections:
            return []

        # Convert the sections (pydantic models) to dicts for JSON
        sections_dict = {k: (v.model_dump() if hasattr(v, 'model_dump') else v) for k, v in sections.items()}
        
        system_instruction = (
            "You are a Chief Strategy Officer. Your task is to perform cross-provider reasoning for "
            f"the company {entity_name}. You are provided with highly structured intelligence sections "
            "(Financials, Competitors, Technology, News, etc.).\n"
            "Identify correlations across these sections (e.g. matching a hiring surge in Technology with a "
            "new product launch in News). Generate 3-5 validated executive signals that combine insights from multiple domains.\n"
            "Return ONLY a JSON object: {'validated_signals': ['Signal 1', 'Signal 2', ...]}."
        )

        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        prompt = f"Sections Data:\n{json.dumps(sections_dict, default=str)[:12000]}"
        
        try:
            parsed = await ProviderRouter.generate_json(
                agent_name="cross_provider_reasoning",
                system_prompt=system_instruction,
                user_prompt=prompt
            )
            return parsed.get("validated_signals", [])
        except Exception as e:
            logger.error(f"CrossProviderReasoningAgent failed: {e}")
            return []
