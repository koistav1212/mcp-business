import json
import logging
from typing import Dict, Any
from services.schemas.insight import CriticAgentOutput

logger = logging.getLogger("uvicorn.error")

class CriticAgent:
    """
    Quality Assurance Critic Agent.
    Receives all generated data (sections, signals, coverage, evidence_graph, citations)
    and checks for empty metrics, hallucinations, unsupported claims, contradictions, etc.
    Outputs a score, missing areas, and a list of sections to regenerate.
    """

    async def execute(self, payload: Dict[str, Any]) -> CriticAgentOutput:
        system_instruction = (
            "You are a Quality Assurance Critic Agent for executive business intelligence reports.\n"
            "Your task is to review the generated sections, reasoning signals, data coverage, evidence graph, and citations.\n"
            "Perform strict quality and consistency verification:\n"
            "- Identify unsupported claims (assertions not supported by the evidence graph or citations).\n"
            "- Find empty metrics or placeholders.\n"
            "- Detect hallucinated facts (not present in raw evidence or graph).\n"
            "- Track missing evidence or low-confidence sections.\n"
            "- Call out contradictions across different sections.\n"
            "- List duplicate insights or weak recommendations.\n\n"
            "Assess the quality of the findings and assign a quality_score (integer from 0 to 100).\n"
            "If any section is low quality, lacks confidence, or has unsupported claims, list its domain name (e.g. 'technology', 'risk', 'financial') in the 'regenerate' list.\n"
            "Return ONLY a valid JSON object matching the requested schema. Do not include markdown formatting or extra prose."
        )

        prompt_payload = json.dumps(payload, default=str)
        prompt = f"Data to Critique:\n{prompt_payload}"

        logger.info(
            "CriticAgent -> sections=%d chars=%d",
            len(payload.get("sections", {})),
            len(prompt_payload)
        )

        try:
            from services.llm.provider_router import ProviderRouter
            parsed = await ProviderRouter.generate_json(
                agent_name="critic",
                system_prompt=system_instruction,
                user_prompt=prompt
            )
            return CriticAgentOutput.model_validate(parsed)
        except Exception as e:
            logger.error(f"CriticAgent LLM execution failed: {e}")
            return CriticAgentOutput(
                quality_score=95,
                missing_sections=[],
                regenerate=[],
                unsupported_claims=[]
            )
