import json
import logging
from services.models.planning_models import PlanningResult
from services.research.json_llm import ModelRouter

logger = logging.getLogger("uvicorn.error")

PLANNER_SYSTEM_PROMPT = """You are a Prompt Understanding Agent in a Business Intelligence platform.
Your task is to analyze the user request and translate it into a structured analysis plan.

Analyze the prompt and output a JSON object exactly matching this schema:
{
  "intent": "string (e.g. sales_strategy, investment_analysis, competitive_analysis, general)",
  "workspace_type": "string (e.g. COMPETITOR_ANALYSIS, MARKET_ENTRY, BUSINESS_CASE, DEEP_RESEARCH)",
  "companies": ["list of strings (e.g. ['Apple', 'Samsung'])"],
  "research_depth": "string (e.g. basic, comprehensive, deep)",
  "report_style": "string (e.g. executive, consulting, academic)",
  "required_outputs": ["list of strings (e.g. ['financial_benchmark', 'board_deck', 'swot_analysis'])"],
  "research_tracks": [
    {
      "agent": "competitor_agent",
      "objective": "Identify competitors"
    },
    {
      "agent": "financial_agent",
      "objective": "Compare revenues"
    },
    {
      "agent": "technology_agent",
      "objective": "Analyze technology stack"
    },
    {
      "agent": "news_agent",
      "objective": "Gather recent news"
    },
    {
      "agent": "industry_agent",
      "objective": "Analyze industry trends"
    },
    {
      "agent": "ai_agent",
      "objective": "Compare AI strategy"
    },
    {
      "agent": "risk_agent",
      "objective": "Identify key risks"
    },
    {
      "agent": "strategy_agent",
      "objective": "Generate recommendations"
    }
  ]
}

Return ONLY the raw JSON object. Do not include markdown formatting.
"""

class PlannerAgent:
    def __init__(self):
        self.model = ModelRouter().planner()

    async def execute(self, user_query: str) -> PlanningResult:
        if self.model:
            try:
                payload = await self.model.generate_json(
                    PLANNER_SYSTEM_PROMPT,
                    json.dumps({"prompt": user_query})
                )
                return PlanningResult.model_validate(payload)
            except Exception as e:
                logger.warning(f"LLM planner failed: {e}. Falling back to basic parsing.")
                
        # Basic heuristic fallback
        return PlanningResult(
            intent="general",
            workspace_type="DEEP_RESEARCH",
            companies=[user_query.strip()[:50]],
            research_depth="comprehensive",
            report_style="executive",
            required_outputs=["executive_summary"],
            research_tracks=[
                {"agent": "competitor_agent", "objective": "Identify top competitors"},
                {"agent": "financial_agent", "objective": "Benchmark revenues and margins"},
                {"agent": "strategy_agent", "objective": "Generate high-level strategic overview"}
            ]
        )
