import json
import logging
from typing import Awaitable, Callable, Optional

from services.schemas.insight import IntentPlan
from services.planning.planner import PromptUnderstandingAgent

logger = logging.getLogger("uvicorn.error")

class IntentEngine:
    """Extracts decision intent; delegates to the PromptUnderstandingAgent."""

    def __init__(self, json_generator: Optional[Callable[[str, str], Awaitable[dict]]] = None):
        self.json_generator = json_generator

    async def extract(self, query: str, entity_hint: Optional[str] = None) -> IntentPlan:
        agent = PromptUnderstandingAgent(json_generator=self.json_generator)
        plan_dict = await agent.plan(query)
        
        # Populate IntentPlan fields
        planner_intent = plan_dict.get("intent", "general")
        intent = {
            "investment_analysis": "investment",
            "financial_analysis": "investment",
            "sales_strategy": "sales pursuit",
        }.get(planner_intent, planner_intent)
        req_sources = plan_dict.get("required_sources", [])
        req_analyses = plan_dict.get("required_analytics", [])
        framework = plan_dict.get("report_framework", "general_brief")
        workspace_type = plan_dict.get("workspace_type", "DEEP_RESEARCH")
        report_style = plan_dict.get("report_style", "executive")
        required_frameworks = plan_dict.get("required_frameworks", [])
        ui_generation_spec = plan_dict.get("ui_generation", {})
        
        # Merge data from required_data directly if provided by the new LLM struct
        explicit_required_data = plan_dict.get("required_data", [])
        
        # Prioritize entity_hint if provided, otherwise fallback to target_company
        target_company = entity_hint or plan_dict.get("target_company") or query.replace("Research ", "").strip()
        
        # Map required_sources to required_data
        required_data = []
        required_data.append("company profile")
        
        # We need to map generic aliases back to required data, just in case
        for src in req_sources:
            src_clean = src.lower()
            if src_clean in ["company"]:
                required_data.append("company profile")
            elif src_clean in ["people"]:
                required_data.append("leadership")
            elif src_clean in ["hiring"]:
                required_data.append("hiring signals")
            elif src_clean in ["competitors"]:
                required_data.extend(["competitive positioning", "swot"])
            elif src_clean in ["news"]:
                required_data.append("recent developments")
            elif src_clean in ["sec", "financials"]:
                required_data.append("financial history")
            elif src_clean in ["yfinance", "market"]:
                required_data.append("market valuation")
            elif src_clean in ["web", "technology"]:
                required_data.append("technology stack")
            elif src_clean in ["social", "social_intel", "reddit"]:
                required_data.append("social sentiment")
            
        required_data.extend(explicit_required_data)
        required_data = list(dict.fromkeys(required_data))
        
        # Calculations & visualizations
        calculations = []
        visualizations = []
        if "valuation" in req_analyses:
            calculations.extend(["revenue growth", "profit growth", "valuation multiples"])
            visualizations.extend(["financial trend", "valuation comparison"])
        if "revenue_growth" in req_analyses or "earnings_growth" in req_analyses:
            calculations.extend(["revenue growth", "profit growth"])
            
        return IntentPlan(
            primary_goal=plan_dict.get("research_goal", query),
            user_persona="investor" if intent == "investment" else "sales leader" if intent == "sales pursuit" else "business decision-maker",
            report_type=framework,
            industry_focus=plan_dict.get("industry", "general"),
            time_horizon=plan_dict.get("time_horizon", "current"),
            depth=plan_dict.get("analysis_depth", "standard"),
            workspace_type=workspace_type,
            report_style=report_style,
            decision_type=intent,
            entities=[target_company] if target_company else [],
            required_data=required_data,
            required_calculations=calculations,
            required_visualizations=visualizations,
            required_sources=req_sources,
            required_frameworks=required_frameworks,
            success_criteria=["answer the stated decision", "support material claims with evidence"],
            ui_generation_spec=ui_generation_spec,
            output_format="json",
            confidence=1.0,
            clarification_needed=False
        )
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
  "user_problem": "The underlying business problem the user wants to solve (e.g. 'Pitch our platform to the target stakeholders')",
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
        if any(w in lowered for w in ("sell", "pitch", "proposal", "sales", "account plan")):
            return ResearchGoal(
                primary_goal="sales",
                user_problem="Pitch our product to the target company's stakeholders",
                desired_output="sales_strategy",
                decision_type="account_based_selling"
            )

        # 2. Investment patterns
        if any(w in lowered for w in ("valuation", "risk", "stock", "invest", "equity")):
            return ResearchGoal(
                primary_goal="investment",
                user_problem="Evaluate whether the target company is an attractive investment today",
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
