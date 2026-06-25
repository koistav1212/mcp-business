import json
import logging
from typing import Dict
from services.models.planning_models import PlanningResult
from services.models.research_models import ResearchMission, AgentResult
from services.research.json_llm import ModelRouter

logger = logging.getLogger("uvicorn.error")

META_SYNTHESIS_PROMPT = """You are a Meta Synthesizer.
Your job is to combine multiple specialized research reports into one cohesive, executive-ready report structure.

Analyze the compiled inputs from all specialized agents and output a JSON object exactly matching this schema:
{
  "executive_summary": "string",
  "company_overview": "string",
  "industry_summary": "string",
  "financial_analysis": "string",
  "competitive_analysis": "string",
  "ai_strategy": "string",
  "technology_analysis": "string",
  "swot": "string",
  "risks": ["list of strings"],
  "opportunities": ["list of strings"],
  "recommendations": ["list of strings"],
  "evidence_gaps": ["list of strings"],
  "appendix": "string",
  "confidence": 0.95
}

Return ONLY the raw JSON object. Do not include markdown formatting.
"""

class SynthesizerAgent:
    def __init__(self):
        self.model = ModelRouter().synthesizer()

    async def execute(self, agent_results: Dict[str, AgentResult], planning: PlanningResult, mission: ResearchMission, company_entity=None):
        # Aggregate the reports (strip evidence to save tokens)
        agent_reports_stripped = {}
        for name, result in agent_results.items():
            result_dict = result.model_dump()
            result_dict.pop("evidence", None)
            agent_reports_stripped[name] = result_dict
            
        aggregated_payload = {
            "planning": planning.model_dump(),
            "agent_reports": agent_reports_stripped
        }
        
        if self.model:
            try:
                payload = await self.model.generate_json(
                    META_SYNTHESIS_PROMPT,
                    json.dumps(aggregated_payload)
                )
                return payload
            except Exception as e:
                logger.warning(f"Meta Synthesizer LLM failed: {e}. Returning fallback.")
                
        # Fallback
        return {
            "executive_summary": "Basic synthesized summary.",
            "company_overview": "",
            "industry_summary": "",
            "financial_analysis": "",
            "competitive_analysis": "",
            "ai_strategy": "",
            "technology_analysis": "",
            "swot": "",
            "risks": [],
            "opportunities": [],
            "recommendations": ["Recommendation 1"],
            "evidence_gaps": [],
            "appendix": "",
            "confidence": 0.5
        }
