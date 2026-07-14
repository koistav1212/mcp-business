import json
from services.research.models import ResearchContext

from ..schemas.data_profile_schema import DataProfile
from ..schemas.insight_schema import InsightPlan

INSIGHT_PLANNER_PROMPT = """You are an Executive Insight Planner.

Given a data profile for a company, decide what executive questions can be answered and propose insight candidates.

Respond with ONLY valid JSON matching this schema:
{
  "page_objective": "string",
  "executive_questions": [
    {
      "id": "string",
      "question": "string",
      "priority": 1,
      "answerability": 0.9,
      "evidence_paths": ["string"]
    }
  ],
  "insight_candidates": [
    {
      "id": "string",
      "insight_type": "string",
      "statement": "string",
      "executive_question_id": "string",
      "evidence_paths": ["string"],
      "confidence": 0.9
    }
  ]
}
"""

class InsightPlanner:
    def __init__(self, model_router=None):
        self.router = model_router

    async def plan(self, context: ResearchContext, data_profile: DataProfile) -> InsightPlan:
        """
        Plans the insights that can be extracted from the data profile.
        """
        payload = {
            "page_type": "executive_company_snapshot",
            "context": context.model_dump(mode="json"),
            "data_profile": data_profile.model_dump(mode="json"),
        }
        
        if not self.router:
            # Fallback mock plan
            return InsightPlan(
                page_objective="Explain corporate identity and strategic architecture",
                executive_questions=[
                    {
                        "id": "Q1",
                        "question": "What is this company and where does it compete?",
                        "priority": 1,
                        "answerability": 0.9,
                        "evidence_paths": ["entity.entity.name", "entity.entity.industry", "profile.overview"],
                    },
                    {
                        "id": "Q2",
                        "question": "How is the business structurally organized?",
                        "priority": 2,
                        "answerability": 0.8,
                        "evidence_paths": ["entity.products", "entity.services", "entity.solutions"],
                    },
                ],
                insight_candidates=[
                    {
                        "id": "INS-001",
                        "insight_type": "strategic_position",
                        "statement": "Operates with a multi-offering platform structure anchored by its core products and services.",
                        "executive_question_id": "Q2",
                        "evidence_paths": ["profile.overview", "entity.products", "entity.services"],
                        "confidence": 0.8,
                    }
                ],
            )

        try:
            model = self.router.ui()
            result = await model.generate_json(
                INSIGHT_PLANNER_PROMPT,
                json.dumps(payload, default=str)
            )
            return InsightPlan.model_validate(result)
        except Exception:
            # Fallback
            return InsightPlan(
                page_objective="Explain corporate identity",
                executive_questions=[],
                insight_candidates=[],
            )
