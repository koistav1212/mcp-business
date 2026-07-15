from __future__ import annotations

from typing import Any, Dict, List
import json
import logging
import httpx
from core.config import settings
from services.llm.provider_router import ProviderRouter

from services.schemas.report import CoverageResult, ReportPageSpec


def _pick(data: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {key: data.get(key) for key in keys if key in data}


class PageContextBuilder:
    PAGE_FIELDS = {
        "executive": ["entity", "profile", "financials", "analytics", "industry_context", "risk_factors", "valuation_multiples", "capital_allocation"],
        "company": ["entity", "profile", "leadership", "competitors", "industry_context"],
        "financial": ["financials", "analytics", "valuation_multiples", "capital_allocation"],
        "market": ["industry_context", "competitors", "news", "social_sentiment"],
        "competition": ["competitors", "competitive_positioning", "swot", "news", "social_sentiment"],
        "technology": ["technology_stack", "news", "hiring_signals", "management_commentary"],
        "customer": ["social_sentiment", "news"],
        "risk": ["risk_factors", "news", "management_commentary", "social_sentiment"],
        "strategy": ["swot", "risk_factors", "industry_context", "capital_allocation", "analytics", "competitors"],
        "appendix": ["evidence_graph", "news", "risk_factors", "technology_stack"],
    }

    def build_page_context(self, spec: ReportPageSpec, context_dict: Dict[str, Any]) -> Dict[str, Any]:
        fields = self.PAGE_FIELDS.get(spec.page_id, [])
        payload = _pick(context_dict, fields)
        payload["page_title"] = spec.title
        payload["page_id"] = spec.page_id
        return payload

    def check_coverage(self, spec: ReportPageSpec, page_context: Dict[str, Any]) -> CoverageResult:
        present = [k for k, v in page_context.items() if k not in {"page_title", "page_id"} and v not in (None, "", [], {})]
        missing = [k for k, v in page_context.items() if k not in {"page_title", "page_id"} and v in (None, "", [], {})]
        total = len(present) + len(missing)
        score = len(present) / total if total else 0.0
        return CoverageResult(page_id=spec.page_id, present_fields=present, missing_fields=missing, coverage_score=score)

logger = logging.getLogger("uvicorn.error")

class InsightPlanner:
    """
    Decides the executive questions to answer on the UI based on the generated intelligence sections.
    Flow: Sections -> Insight Planner -> Questions -> Components
    """
    async def plan(self, sections: Dict[str, Any], narratives: Dict[str, str], entity_name: str) -> List[Dict[str, Any]]:
        sections_dict = {k: (v.model_dump() if hasattr(v, 'model_dump') else v) for k, v in sections.items()}
        
        system_instruction = (
            "You are a UI Experience Planner. Based on the business intelligence sections and narratives provided, "
            f"determine the top 4-6 executive questions that the dashboard for {entity_name} should answer.\n"
            "For each question, recommend the type of component (e.g. 'comparison_matrix', 'timeline', 'metric_cards', 'narrative_block').\n"
            "Return ONLY a JSON list of objects: [{'question': 'Why is the company winning?', 'component_type': 'narrative_block'}, ...]"
        )

        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "narratives": narratives,
            "sections": sections_dict
        }
        
        prompt = f"Data for UI Planning:\n{json.dumps(payload, default=str)[:16000]}"
        
        try:
            parsed = await ProviderRouter.generate_json(
                agent_name="insight_planner",
                system_prompt=system_instruction,
                user_prompt=prompt
            )
            # the prompt asked for a JSON list, but response_format json_object requires an object.
            # we'll assume it returns {"questions": [...]} based on common LLM behavior or we can parse it if it returned a list directly
            if "questions" in parsed:
                return parsed["questions"]
            return parsed
        except Exception as e:
            logger.error(f"InsightPlanner failed: {e}")
            return []
