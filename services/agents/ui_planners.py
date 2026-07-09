import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

PRESENTATION_PLANNER_PROMPT = """
You are a Presentation Planner for executive business reviews.
Input: A JSON payload containing research context (company data, financials, risks, markets).
Your job is NOT to design slides or charts.
Your job is only to decide:
1. What type of presentation this is.
2. What major story beats it should cover.
3. In what order.

Every item in the storyline must represent one executive business question or theme.

Output JSON:
{
  "presentation_type": "CEO_REPORT",
  "target_executive": "CEO",
  "time_horizon": "12M",
  "storyline": [
    {
      "id": "exec_summary",
      "title": "Executive Summary",
      "question": "What is the high-level health and outlook of the company?",
      "priority": "critical"
    }
  ]
}
"""

SLIDE_PLANNER_PROMPT = """
You are a Slide Planner for executive decks.
For each storyline item, design one slide.
Do NOT pick charts or layouts.
For each slide decide:
- title
- goal (what understanding the executive should gain)
- decision (what decision this slide informs)
- required_data (keys from the context needed to support this, e.g. "financials.revenue_history")
- question (the slide-level business question)
- decision_priority ("critical", "high", "supporting")

Output for the requested storyline item:
{
  "slide_id": "financial_quality",
  "title": "Financial Performance",
  "goal": "Explain whether revenue and margins are improving or deteriorating.",
  "decision": "Should leadership be optimistic about financial momentum?",
  "question": "Is this business improving over time?",
  "required_data": [
    "financials.revenue_history",
    "financials.margin_history"
  ],
  "decision_priority": "critical",
  "time_horizon": "12M"
}
"""

class PresentationPlanner:
    def __init__(self, model_router=None):
        self.router = model_router

    async def execute(self, payload: dict) -> dict:
        if not self.router:
            return self._fallback_plan()
        
        try:
            model = self.router.ui()
            result = await model.generate_json(
                PRESENTATION_PLANNER_PROMPT,
                json.dumps(payload, default=str)
            )
            return result
        except Exception as e:
            logger.error(f"PresentationPlanner failed: {e}")
            return self._fallback_plan()

    def _fallback_plan(self) -> dict:
        return {
            "presentation_type": "CEO_REPORT",
            "target_executive": "CEO",
            "time_horizon": "12M",
            "storyline": [
                {
                    "id": "exec_summary",
                    "title": "Executive Summary",
                    "question": "What is the high-level health and outlook of the company?",
                    "priority": "critical"
                },
                {
                    "id": "financial_quality",
                    "title": "Financial Quality",
                    "question": "Is the financial performance improving and sustainable?",
                    "priority": "critical"
                }
            ]
        }

class SlidePlanner:
    def __init__(self, model_router=None):
        self.router = model_router

    async def execute(self, storyline_item: dict, payload: dict) -> dict:
        if not self.router:
            return self._fallback_plan(storyline_item)
            
        user_prompt = {
            "storyline_item": storyline_item,
            "context_summary": {k: v for k, v in payload.items() if k not in ["evidence_graph", "news"]}
        }
        
        try:
            model = self.router.ui()
            result = await model.generate_json(
                SLIDE_PLANNER_PROMPT,
                json.dumps(user_prompt, default=str)
            )
            # Ensure slide_id is present
            if "slide_id" not in result:
                result["slide_id"] = storyline_item.get("id", "slide")
            return result
        except Exception as e:
            logger.error(f"SlidePlanner failed for {storyline_item.get('id')}: {e}")
            return self._fallback_plan(storyline_item)

    def _fallback_plan(self, storyline_item: dict) -> dict:
        return {
            "slide_id": storyline_item.get("id", "slide"),
            "title": storyline_item.get("title", "Overview"),
            "goal": "Provide high-level context.",
            "decision": "Determine next areas of investigation.",
            "question": storyline_item.get("question", "What is the current state?"),
            "required_data": ["profile"],
            "decision_priority": storyline_item.get("priority", "high"),
            "time_horizon": "12M"
        }
