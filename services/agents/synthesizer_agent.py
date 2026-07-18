import json
import logging
from typing import Dict, Any, List
from services.schemas.insight import ExecutiveSynthesizerOutput

logger = logging.getLogger("uvicorn.error")

class SynthesizerAgent:
    """
    Executive Synthesizer Agent.
    The only agent allowed to write narrative prose (Executive Summary, Investment Case,
    Strategic Outlook, Key Risks, Opportunities, Recommendations).
    Receives validated sections, validated signals, and quality score (never raw data).
    """

    async def execute(self, validated_sections: Dict[str, Any], validated_signals: List[str], quality_score: int, entity_name: str) -> Dict[str, Any]:
        system_instruction = (
            "You are the Lead Executive Analyst (Executive Synthesizer). Your task is to generate the final executive narratives "
            f"for the company {entity_name} based on the validated section outputs, signals, and quality score provided.\n"
            "CRITICAL RULES:\n"
            "- You are the ONLY agent in this architecture allowed to write narrative prose.\n"
            "- Write professional, high-impact narrative blocks for each of: 'executive_summary', 'investment_case', "
            "'strategic_outlook', 'key_risks', 'opportunities', and 'recommendations'.\n"
            "- Ground all narratives strictly in the provided validated sections and signals. Do not invent any facts, numbers, or details.\n"
            "- You MUST extract real source URLs and evidence references from the inputs and populate the 'evidence_refs' array.\n"
            "- Do NOT put narrative opinion sentences into the 'evidence_refs' array. Only include real citations, URLs, and source metadata.\n"
            "Return ONLY a valid JSON object matching the requested schema. Do not include markdown formatting or extra prose outside the JSON."
        )

        payload = {
            "validated_sections": validated_sections,
            "validated_signals": validated_signals,
            "quality_score": quality_score
        }

        prompt_payload = json.dumps(payload, default=str)
        prompt = f"Data for Synthesis:\n{prompt_payload}"

        logger.info(
            "Synthesizer -> sections=%d signals=%d chars=%d",
            len(validated_sections),
            len(validated_signals),
            len(prompt_payload)
        )

        try:
            from services.llm.provider_router import ProviderRouter
            parsed = await ProviderRouter.generate_json(
                agent_name="synthesizer",
                system_prompt=system_instruction,
                user_prompt=prompt
            )
            
            # Make sure it matches our schema
            validated = ExecutiveSynthesizerOutput.model_validate(parsed)
            return validated.model_dump()
        except Exception as e:
            logger.error(f"SynthesizerAgent failed: {e}")
            return {
                "executive_summary": "Summary unavailable.",
                "investment_case": "Investment case unavailable.",
                "strategic_outlook": "Strategic outlook unavailable.",
                "key_risks": "Key risks unavailable.",
                "opportunities": "Opportunities unavailable.",
                "recommendations": "Recommendations unavailable."
            }
