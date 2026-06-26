import json
import logging
from typing import Any, Awaitable, Callable, Dict, Optional
from pydantic import BaseModel

from services.llm.provider_router import ProviderRouter

logger = logging.getLogger("uvicorn.error")

GOAL_EXTRACTOR_SYSTEM_PROMPT = """You are a Goal Extraction Agent in a business intelligence framework.
Analyze the user prompt and extract the core research goals into JSON format.

JSON schema:
{
  "primary_goal": "A short category of the goal (e.g. 'sales', 'investment', 'market_entry', 'product_strategy')",
  "user_problem": "The underlying business problem the user wants to solve (e.g. 'Pitch TalentIQ platform to Zoho stakeholders')",
  "desired_output": "The type of strategy/analysis output requested (e.g. 'sales_strategy', 'equity_research', 'market_report')",
  "decision_type": "The business decision context (e.g. 'account_based_selling', 'stock_investment', 'market_expansion')"
}

Return ONLY the raw JSON object. Do not include markdown code block formatting (like ```json ... ```).
"""

class ResearchGoal(BaseModel):
    primary_goal: str
    user_problem: str
    desired_output: str
    decision_type: str

class GoalExtractor:
    """
    Extracts high-level goals, problems, desired outputs, and decision types from raw user requests.
    """
    async def extract(self, prompt: str) -> ResearchGoal:
        """
        Extracts research goals from the prompt.
        Uses Multi-Provider routing, otherwise falls back to heuristics.
        """
        if True:
            try:
                payload = await ProviderRouter.generate_json(
                    agent_name="planner",
                    system_prompt=GOAL_EXTRACTOR_SYSTEM_PROMPT,
                    user_prompt=json.dumps({"prompt": prompt})
                )
                return ResearchGoal.model_validate(payload)
            except Exception as e:
                logger.warning(f"LLM goal extraction failed: {e}. Falling back to heuristics.")

        return self._heuristic_extract(prompt)

    def _heuristic_extract(self, prompt: str) -> ResearchGoal:
        """
        Fallback heuristic parser for goal extraction.
        """
        lowered = prompt.lower().strip()

        # 1. Sales patterns
        if any(w in lowered for w in ("sell", "zoho", "pitch", "proposal", "sales", "account plan")):
            target = "Zoho" if "zoho" in lowered else "NVIDIA" if "nvidia" in lowered else "the target company"
            product = "TalentIQ" if "talentiq" in lowered else "our product"
            return ResearchGoal(
                primary_goal="sales",
                user_problem=f"Pitch {product} platform to {target} stakeholders",
                desired_output="sales_strategy",
                decision_type="account_based_selling"
            )

        # 2. Investment patterns
        if any(w in lowered for w in ("nvidia", "valuation", "risk", "stock", "invest", "equity")):
            target = "NVIDIA" if "nvidia" in lowered else "the target company"
            return ResearchGoal(
                primary_goal="investment",
                user_problem=f"Evaluate whether {target} is an attractive investment today",
                desired_output="equity_research",
                decision_type="stock_investment"
            )

        # Default fallback
        return ResearchGoal(
            primary_goal="general_research",
            user_problem=f"Compile business intelligence context for: {prompt}",
            desired_output="general_brief",
            decision_type="informational"
        )
