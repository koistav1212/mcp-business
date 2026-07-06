from __future__ import annotations

from typing import Any, Dict, List

from services.reports.models import CoverageResult, ReportPageSpec


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
