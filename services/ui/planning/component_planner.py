import json
from services.schemas.insight import ResearchContext

from ..registry.component_registry import component_registry
from ..schemas.component_plan_schema import ComponentPlan
from ..schemas.data_profile_schema import DataProfile
from ..schemas.insight_schema import InsightPlan

COMPONENT_PLANNER_PROMPT = """You are a Component Planner for business intelligence pages.

Given a Data Profile, an Insight Plan, and the COMPONENT CATALOG, select the best components to answer the executive questions.
You must select components across ALL 8 executive questions (which map to 8 pages) if the data is available.
- For Q5 (News), strongly prefer `NewsTimeline`.
- For Q8 (Knowledge Graph), strongly prefer `KnowledgeGraphViewer`.

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
        
        default_components = [
            # Page 1 (Q1)
            {"component_type": "ExecutiveHero", "executive_question_id": "Q1", "insight_ids": [], "priority": 1, "span": 12},
            {"component_type": "MetricStrip", "executive_question_id": "Q1", "insight_ids": [], "priority": 2, "span": 12},
            {"component_type": "BusinessArchitectureMap", "executive_question_id": "Q1", "insight_ids": [], "priority": 3, "span": 7},
            {"component_type": "FactMatrix", "executive_question_id": "Q1", "insight_ids": [], "priority": 4, "span": 5},
            
            # Page 2 (Q2)
            {"component_type": "FinancialHealthScorecard", "executive_question_id": "Q2", "insight_ids": [], "priority": 1, "span": 12},
            
            # Page 3 (Q3)
            {"component_type": "StrategicPositionCard", "executive_question_id": "Q3", "insight_ids": [], "priority": 1, "span": 12},
            
            # Page 4 (Q4)
            {"component_type": "PlatformStackMap", "executive_question_id": "Q4", "insight_ids": [], "priority": 1, "span": 12},
            
            # Page 5 (Q5)
            {"component_type": "NewsTimeline", "executive_question_id": "Q5", "insight_ids": [], "priority": 1, "span": 12},
            
            # Page 6 (Q6)
            {"component_type": "RiskMatrix", "executive_question_id": "Q6", "insight_ids": [], "priority": 1, "span": 12},
            
            # Page 7 (Q7)
            {"component_type": "SentimentTimeline", "executive_question_id": "Q7", "insight_ids": [], "priority": 1, "span": 12},
            
            # Page 8 (Q8)
            {"component_type": "KnowledgeGraphViewer", "executive_question_id": "Q8", "insight_ids": [], "priority": 1, "span": 12},
        ]

        if not self.router:
            # Fallback mock
            return ComponentPlan(selected_components=default_components)

        try:
            model = self.router.ui()
            result = await model.generate_json(
                COMPONENT_PLANNER_PROMPT,
                json.dumps(payload, default=str)
            )
            parsed = ComponentPlan.model_validate(result)
            
            # Ensure critical components are present if data exists and LLM missed them
            has_q8 = any(c.executive_question_id == "Q8" for c in parsed.selected_components)
            if not has_q8 and data_profile.knowledge_graph:
                parsed.selected_components.append(PlannedComponent(component_type="KnowledgeGraphViewer", executive_question_id="Q8", insight_ids=[], priority=1, span=12))
                
            has_q5 = any(c.executive_question_id == "Q5" for c in parsed.selected_components)
            if not has_q5 and data_profile.news:
                parsed.selected_components.append(PlannedComponent(component_type="NewsTimeline", executive_question_id="Q5", insight_ids=[], priority=1, span=12))
                
            return parsed
        except Exception:
            # Fallback
            return ComponentPlan(selected_components=default_components)
