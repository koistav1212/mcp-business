import json
from services.research.models import ResearchContext

from ..registry.component_registry import component_registry
from ..schemas.component_plan_schema import ComponentPlan
from ..schemas.data_profile_schema import DataProfile
from ..schemas.insight_schema import InsightPlan

COMPONENT_PLANNER_PROMPT = """You are a Component Planner for business intelligence pages.

Given a Data Profile, an Insight Plan, and the COMPONENT CATALOG, select the best components to answer the executive questions.

You must respond with ONLY valid JSON matching this schema:
{
  "selected_components": [
    {
      "component_type": "string",
      "executive_question_id": "string",
      "insight_ids": ["string"],
      "priority": 1,
      "span": 12
    }
  ]
}
"""

class ComponentPlanner:
    def __init__(self, model_router=None):
        self.router = model_router
        self.catalog = component_registry.list_components()

    async def plan(
        self,
        context: ResearchContext,
        data_profile: DataProfile,
        insight_plan: InsightPlan,
    ) -> ComponentPlan:
        """
        Plans the UI components based on the data profile and insight plan.
        """
        payload = {
            "context": context.model_dump(mode="json"),
            "data_profile": data_profile.model_dump(mode="json"),
            "insight_plan": insight_plan.model_dump(mode="json"),
            "component_catalog": self.catalog
        }

        if not self.router:
            # Fallback mock
            return ComponentPlan(
                selected_components=[
                    {"component_type": "ExecutiveHero", "executive_question_id": "Q1", "insight_ids": [], "priority": 1, "span": 12},
                    {"component_type": "MetricStrip", "executive_question_id": "Q1", "insight_ids": [], "priority": 2, "span": 12},
                    {"component_type": "BusinessArchitectureMap", "executive_question_id": "Q2", "insight_ids": ["INS-001"], "priority": 3, "span": 7},
                    {"component_type": "StrategicPositionCard", "executive_question_id": "Q2", "insight_ids": ["INS-001"], "priority": 4, "span": 5},
                    {"component_type": "FactMatrix", "executive_question_id": "Q1", "insight_ids": [], "priority": 5, "span": 5},
                ],
            )

        try:
            model = self.router.ui()
            result = await model.generate_json(
                COMPONENT_PLANNER_PROMPT,
                json.dumps(payload, default=str)
            )
            return ComponentPlan.model_validate(result)
        except Exception:
            # Fallback
            return ComponentPlan(selected_components=[])
