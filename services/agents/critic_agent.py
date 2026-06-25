import json
import logging
from services.research.json_llm import ModelRouter

logger = logging.getLogger("uvicorn.error")

CRITIC_SYSTEM_PROMPT = """You are a Critic Agent. 
Review the drafted report synthesis against the original request and provide constructive feedback.

Output schema must EXACTLY be:
{
    "score": 0.85,
    "feedback": ["list of constructive feedback"],
    "missing_data": ["list of missing data points"],
    "hallucinations_detected": ["list of potential hallucinations"],
    "checks": {
        "were_financials_present": true,
        "were_competitors_analyzed": true,
        "did_recommendations_cite_evidence": true,
        "were_required_sections_omitted": false,
        "did_synthesis_invent_numbers": false
    },
    "coverage_score": 0.9,
    "completeness_score": 0.8
}

Return ONLY the raw JSON object. Do not include markdown formatting.
"""

class CriticAgent:
    def __init__(self):
        self.model = ModelRouter().critic()

    async def review(self, context):
        if not context:
            return None
            
        original_request = context.get("planning", {}).get("goal", "Unknown Request")
        payload_data = {
            "original_request": original_request,
            "drafted_synthesis": context
        }
        
        if self.model:
            try:
                payload = await self.model.generate_json(
                    CRITIC_SYSTEM_PROMPT,
                    json.dumps(payload_data)
                )
                return payload
            except Exception as e:
                logger.warning(f"Critic LLM failed: {e}. Returning fallback.")
                
        # Fallback
        return {
            "score": 0.5,
            "feedback": ["Basic feedback"],
            "missing_data": [],
            "hallucinations_detected": [],
            "checks": {
                "were_financials_present": False,
                "were_competitors_analyzed": False,
                "did_recommendations_cite_evidence": False,
                "were_required_sections_omitted": True,
                "did_synthesis_invent_numbers": False
            },
            "coverage_score": 0.5,
            "completeness_score": 0.5
        }
