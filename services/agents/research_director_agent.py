import json
import logging
from services.models.planning_models import PlanningResult
from services.models.research_models import ResearchMission
from services.research.json_llm import ModelRouter

logger = logging.getLogger("uvicorn.error")

DIRECTOR_SYSTEM_PROMPT = """You are a Research Director orchestrating a Multi-Agent System.
Given the PlanningResult which contains 'research_tracks' (the agents and their objectives), your task is to finalize the list of specialized research agents to spawn and determine the number of iterative passes needed to complete the research mission.
CRITICAL: Do NOT just copy the planner's tracks unchanged. You must EXPAND the tracks into a broader, comprehensive set of agents. For example, if planner says 'competitive analysis', you should activate financial, technology, ai, industry, news, leadership, valuation, risk, competitor, and strategy agents.

Available Agents:
- financial_agent, competitor_agent, industry_agent, news_agent, technology_agent, risk_agent, mna_agent, valuation_agent, growth_agent, ai_agent, strategy_agent

Analyze the plan and output a JSON object exactly matching this schema:
{
  "agents": ["list of string agent names"],
  "tracks": [
    {
      "agent": "string",
      "objective": "string"
    }
  ],
  "iterations": int (2 or 3 for deep research, 1 for simple),
  "minimum_sources": int (e.g. 5 to 40)
}

Return ONLY the raw JSON object. Do not include markdown formatting.
"""

class ResearchDirectorAgent:
    def __init__(self):
        self.model = ModelRouter().director()

    async def execute(self, planning: PlanningResult) -> ResearchMission:
        if self.model:
            try:
                payload = await self.model.generate_json(
                    DIRECTOR_SYSTEM_PROMPT,
                    json.dumps(planning.model_dump())
                )
                return ResearchMission.model_validate(payload)
            except Exception as e:
                logger.warning(f"LLM director failed: {e}. Falling back to research_tracks logic.")
                
        # Use planner's research tracks directly as fallback
        tracks = planning.research_tracks if hasattr(planning, "research_tracks") and planning.research_tracks else []
        agents = [track.agent for track in tracks]
        if not agents:
            # Fallback to simple default
            agents = ["news_agent", "industry_agent"]
            tracks = [
                {"agent": "news_agent", "objective": "Gather recent news"},
                {"agent": "industry_agent", "objective": "Analyze industry trends"}
            ]
            
        # Ensure unique agents while keeping order roughly intact
        unique_agents = []
        for a in agents:
            if a not in unique_agents:
                unique_agents.append(a)
                
        tracks_dicts = [t.model_dump() if hasattr(t, "model_dump") else t for t in tracks]
        return ResearchMission(
            agents=unique_agents,
            tracks=tracks_dicts,
            iterations=2, # Default to 2 iterative passes as requested
            minimum_sources=len(unique_agents) * 3
        )
