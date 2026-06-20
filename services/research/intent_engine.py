import json
import logging
from typing import Awaitable, Callable, Optional

from services.research.models import IntentPlan
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
        
        # Prioritize entity_hint if provided, otherwise fallback to target_company
        target_company = entity_hint or plan_dict.get("target_company")
        
        # Map required_sources to required_data
        required_data = []
        required_data.append("company profile")
        if "people" in req_sources:
            required_data.append("leadership")
        if "hiring" in req_sources:
            required_data.append("hiring signals")
        if "competitors" in req_sources:
            required_data.extend(["competitive positioning", "swot"])
        if "news" in req_sources:
            required_data.append("recent developments")
        if "sec" in req_sources:
            required_data.append("financial history")
        if "yfinance" in req_sources:
            required_data.append("market valuation")
        if "web" in req_sources or "competitors" in req_sources:
            required_data.append("technology stack")
            
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
            decision_type=intent,
            entities=[target_company] if target_company else [],
            required_data=required_data,
            required_calculations=calculations,
            required_visualizations=visualizations,
            required_sources=req_sources,
            success_criteria=["answer the stated decision", "support material claims with evidence"],
            output_format="json",
            confidence=1.0,
            clarification_needed=False
        )
