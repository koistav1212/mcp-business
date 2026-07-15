from __future__ import annotations

from services.core.models import ResearchExecutionPlan
from services.schemas.report import ReportPageSpec, ReportPlan


class ReportPageRouter:
    def route(self, plan: ResearchExecutionPlan, context_dict: dict) -> ReportPlan:
        workspace = (plan.workspace_type or "").upper()
        goal = (plan.goal or "").lower()

        if workspace in {"MARKET_RESEARCH", "SECTOR_PULSE"} or "market" in goal or "consumer" in goal:
            return ReportPlan(
                report_type="market",
                pages=[
                    ReportPageSpec("executive", "Executive Summary", "executive", "executive"),
                    ReportPageSpec("company", "Brand or Company Overview", "company", "company"),
                    ReportPageSpec("customer", "Customer Signals", "customer", "customer"),
                    ReportPageSpec("competition", "Competition", "competition", "competition"),
                    ReportPageSpec("market", "Market Context", "market", "market"),
                    ReportPageSpec("strategy", "Strategy and Recommendations", "strategy", "strategy"),
                    ReportPageSpec("appendix", "Appendix", "appendix", "appendix"),
                ],
            )

        return ReportPlan(
            report_type="company_financial",
            pages=[
                ReportPageSpec("executive", "Executive Summary", "executive", "executive"),
                ReportPageSpec("company", "Company Overview", "company", "company"),
                ReportPageSpec("financial", "Financial Performance", "financial", "financial"),
                ReportPageSpec("market", "Market Context", "market", "market"),
                ReportPageSpec("competition", "Competition", "competition", "competition"),
                ReportPageSpec("technology", "Technology", "technology", "technology"),
                ReportPageSpec("risk", "Risks", "risk", "risk"),
                ReportPageSpec("strategy", "Strategy and Recommendations", "strategy", "strategy"),
                ReportPageSpec("appendix", "Appendix", "appendix", "appendix"),
            ],
        )
