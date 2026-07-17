import json
import logging
from typing import Dict, Any, List
from services.llm.provider_router import ProviderRouter

logger = logging.getLogger("uvicorn.error")

class CrossProviderReasoningAgent:
    """
    Consumes structured section outputs and correlates them to generate validated executive signals.
    Receives only structured outputs (financial, technology, competition, operations, products, social, risk),
    identifying correlations, contradictions, hidden opportunities, and strategic themes.
    """

    async def execute(self, sections_dict: Dict[str, Any], entity_name: str) -> List[str]:
        if not sections_dict:
            logger.warning("CrossProviderReasoningAgent: No sections data provided.")
            return []

        system_instruction = (
            "You are a Chief Strategy Officer. Your task is to perform cross-provider reasoning for "
            f"the company {entity_name}. You are provided with highly structured section outputs: "
            "financial, technology, competition, operations, products, social, and risk.\n"
            "Task:\n"
            "- Find correlations across these sections.\n"
            "- Find contradictions across these sections.\n"
            "- Find hidden opportunities.\n"
            "- Find strategic themes.\n"
            "- Validate consistency.\n\n"
            "Return ONLY a JSON object: {'validated_signals': ['Signal 1', 'Signal 2', ...]}."
        )

        prompt_payload = json.dumps(sections_dict, default=str)
        prompt = f"Sections Data:\n{prompt_payload}"

        logger.info(
            "CrossProviderReasoning -> sections=%d chars=%d",
            len(sections_dict),
            len(prompt_payload)
        )

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
