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
    Decides the executive questions to answer on the UI based on the validated intelligence sections.
    Flow: Sections -> UI Planner -> Slide Mapping -> Components
    """
    async def plan(self, validated_sections: Dict[str, Any], narratives: Dict[str, str], entity_name: str) -> List[Dict[str, Any]]:
        sections_dict = {k: (v.model_dump() if hasattr(v, 'model_dump') else v) for k, v in validated_sections.items()}
        
        component_registry = [
            {"component": "RevenueLineChart", "description": "Plots history of revenue"},
            {"component": "MarginAreaChart", "description": "Plots gross margin trends"},
            {"component": "CompetitorTable", "description": "Feature and metric comparison matrix for competitors"},
            {"component": "RiskMatrix", "description": "Maps risk likelihood vs impact"},
            {"component": "NewsTimeline", "description": "Displays product launches or news events over time"},
            {"component": "LeadershipTeam", "description": "Renders organizational leadership hierarchy and executives"},
            {"component": "KpiCards", "description": "Renders key summary statistics and KPI metrics"},
            {"component": "PlatformStackMap", "description": "Maps technology stack and engineering tools"},
            {"component": "SourcesCitations", "description": "Renders citations and source bibliography list"}
        ]

        system_instruction = (
            "You are a UI Experience Planner. Based on the validated sections, component registry, and design templates provided, "
            f"determine the top 4-6 executive questions that the dashboard for {entity_name} should answer.\n"
            "Your job is strictly to map analytical data from the validated sections to the matching components in the registry:\n"
            "- Revenue history -> RevenueLineChart\n"
            "- Gross margin trend -> MarginAreaChart\n"
            "- Competitor feature matrix -> CompetitorTable\n"
            "- Risk likelihood x impact -> RiskMatrix\n"
            "- Product launches over time -> NewsTimeline\n"
            "- Leadership hierarchy -> LeadershipTeam\n"
            "- KPI summary -> KpiCards\n"
            "- Technology stack -> PlatformStackMap\n"
            "- Citations -> SourcesCitations\n\n"
            "Do NOT invent widgets. Only map questions to components listed in the component registry.\n"
            "Return ONLY a JSON list of objects: [{'question': '...', 'component_type': 'RevenueLineChart'}, ...]"
        )

        payload = {
            "validated_sections": sections_dict,
            "component_registry": component_registry,
            "design_system": {"theme": "dark/glassmorphism", "density": "comfortable"},
            "page_templates": ["CEO Intelligence Report", "Competitor Matrix Board", "Operational Risk Analysis"]
        }
        
        prompt = f"Data for UI Planning:\n{json.dumps(payload, default=str)[:16000]}"
        
        try:
            parsed = await ProviderRouter.generate_json(
                agent_name="insight_planner",
                system_prompt=system_instruction,
                user_prompt=prompt
            )
            if "questions" in parsed:
                return parsed["questions"]
            return parsed
        except Exception as e:
            logger.error(f"InsightPlanner failed: {e}")
            return []
