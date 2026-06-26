import json
import logging
from typing import Dict, Any
from services.models.planning_models import PlanningResult
from services.models.research_models import AgentResult
from services.llm.provider_router import ProviderRouter

logger = logging.getLogger("uvicorn.error")

META_SYNTHESIS_PROMPT = """You are a Senior Partner at McKinsey.
Inputs are evidence-backed findings.
Do NOT summarize.

Instead construct a highly synthesized report focusing on insight, narrative, and actionable recommendations.
Each statement must reference evidence IDs.
Never invent facts.
Never restate agent outputs verbatim.
Synthesize. Highlight contradictions. Explain why. State confidence. State missing evidence.

Output schema must be valid JSON:
{
  "executive_summary": "string",
  "company_story": "string",
  "industry_story": "string",
  "financial_story": "string",
  "competition_story": "string",
  "technology_story": "string",
  "ai_story": "string",
  "risk_story": "string",
  "strategic_priorities": ["list of strings"],
  "recommendations": ["list of strings"],
  "implementation_roadmap": ["list of strings"],
  "evidence_appendix": ["list of strings"],
  "confidence": 0.95,
  "missing_evidence": ["list of strings"]
}

Return ONLY the raw JSON object. Do not include markdown formatting.
"""

class SynthesizerAgent:
    async def execute(self, agent_results: Dict[str, Any], planning: PlanningResult, unused_mission=None, company_entity=None):
        # Aggregate the reports (strip evidence to save tokens)
        agent_reports_stripped = {}
        for name, result in agent_results.items():
            if hasattr(result, "model_dump"):
                result_dict = result.model_dump()
                result_dict.pop("evidence", None)
                agent_reports_stripped[name] = result_dict
            else:
                agent_reports_stripped[name] = {"findings": result.findings} if hasattr(result, "findings") else str(result)
            
        aggregated_payload = {
            "planning": planning.model_dump() if hasattr(planning, "model_dump") else {},
            "agent_reports": agent_reports_stripped
        }
        
        if True:
            try:
                payload = await ProviderRouter.generate_json(
                    agent_name="synthesizer",
                    system_prompt=META_SYNTHESIS_PROMPT,
                    user_prompt=json.dumps(aggregated_payload)
                )
                return payload
            except Exception as e:
                logger.warning(f"Meta Synthesizer LLM failed: {e}. Returning fallback.")
                
        # Fallback
        return {
            "executive_summary": "Basic synthesized summary.",
            "company_story": "",
            "industry_story": "",
            "financial_story": "",
            "competition_story": "",
            "technology_story": "",
            "ai_story": "",
            "risk_story": "",
            "strategic_priorities": [],
            "recommendations": ["Recommendation 1"],
            "implementation_roadmap": [],
            "evidence_appendix": [],
            "confidence": 0.5,
            "missing_evidence": []
        }
