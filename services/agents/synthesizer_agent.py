import json
import logging
from typing import Dict, Any, List
import httpx
from core.config import settings
from services.schemas.insight import ExecutiveSummary

logger = logging.getLogger("uvicorn.error")

class SynthesizerAgent:
    """
    The final executive reasoning layer.
    Consumes structured section outputs and reasoning signals to produce cross-sectional insights
    and populates the NarrativeStore.
    """
    async def execute(self, sections: Dict[str, Any], validated_signals: List[str], entity_name: str) -> Dict[str, Any]:
        sections_dict = {k: (v.model_dump() if hasattr(v, 'model_dump') else v) for k, v in sections.items()}
        
        system_instruction = (
            "You are the Lead Executive Analyst. Your task is to generate the final executive narratives "
            f"for the company {entity_name} based on the detailed section intelligence and cross-provider signals provided.\n"
            "Produce the following narratives: 'company_summary', 'investment_case', 'risk_summary', "
            "'competitive_summary', and 'operating_summary'.\n"
            "Return a JSON object with these keys, containing the respective narrative paragraphs."
        )

        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "sections": sections_dict,
            "validated_signals": validated_signals
        }
        
        prompt = f"Data for Synthesis:\n{json.dumps(payload, default=str)[:16000]}"
        
        try:
            from services.llm.provider_router import ProviderRouter
            narratives = await ProviderRouter.generate_json(
                agent_name="synthesizer",
                system_prompt=system_instruction,
                user_prompt=prompt
            )
                
                # We return the narratives to be stored in NarrativeStore by the HostAgent
            return narratives
        except Exception as e:
            logger.error(f"SynthesizerAgent failed: {e}")
            return {}
