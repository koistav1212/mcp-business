from __future__ import annotations

import asyncio
import os
import re
from typing import Dict, List

from services.models.research_execution_plan import ResearchExecutionPlan
from services.reports.composer import ReportComposer
from services.reports.context_builder import PageContextBuilder
from services.reports.coverage_checker import CoverageChecker
from services.reports.critic import ReportCritic
from services.reports.editor import ReportEditor
from services.reports.models import GeneratedPage, ReportOutput
from services.reports.page_router import ReportPageRouter
from services.reports.pages.appendix_agent import AppendixPageAgent
from services.reports.pages.company_agent import CompanyPageAgent
from services.reports.pages.competition_agent import CompetitionPageAgent
from services.reports.pages.customer_agent import CustomerPageAgent
from services.reports.pages.executive_agent import ExecutivePageAgent
from services.reports.pages.financial_agent import FinancialPageAgent
from services.reports.pages.market_agent import MarketPageAgent
from services.reports.pages.risk_agent import RiskPageAgent
from services.reports.pages.strategy_agent import StrategyPageAgent
from services.reports.pages.technology_agent import TechnologyPageAgent


class ReportCoordinator:
    def __init__(self):
        self.router = ReportPageRouter()
        self.context_builder = PageContextBuilder()
        self.coverage_checker = CoverageChecker()
        self.validator = __import__("services.reports.validator", fromlist=["ReportValidator"]).ReportValidator()
        self.critic = ReportCritic()
        self.editor = ReportEditor()
        self.composer = ReportComposer()
        self.page_agents = {
            "executive": ExecutivePageAgent(),
            "company": CompanyPageAgent(),
            "financial": FinancialPageAgent(),
            "market": MarketPageAgent(),
            "competition": CompetitionPageAgent(),
            "technology": TechnologyPageAgent(),
            "customer": CustomerPageAgent(),
            "risk": RiskPageAgent(),
            "strategy": StrategyPageAgent(),
            "appendix": AppendixPageAgent(),
        }
        self.max_parallel_pages = max(1, int(os.environ.get("REPORT_PAGE_CONCURRENCY", "2")))

    async def execute(self, plan: ResearchExecutionPlan, context_dict: Dict, company_entity: str | None = None) -> Dict:
        report_plan = self.router.route(plan, context_dict)

        coverage_results = []
        tasks = []
        semaphore = asyncio.Semaphore(self.max_parallel_pages)

        async def _run_page(spec, page_context, agent):
            async with semaphore:
                return await agent.generate(spec, page_context)

        for spec in report_plan.pages:
            page_context = self.context_builder.build_page_context(spec, context_dict)
            coverage_results.append(self.context_builder.check_coverage(spec, page_context))
            agent = self.page_agents[spec.agent_name]
            tasks.append(_run_page(spec, page_context, agent))

        pages: List[GeneratedPage] = await asyncio.gather(*tasks)
        validation_issues = self.validator.validate(pages)
        critique = self.critic.review(pages)
        coverage_gaps = self.coverage_checker.summarize(coverage_results)

        markdown = self.editor.polish(self.composer.compose(pages))

        findings = self._bullets_from_page(pages, "financial") or self._bullets_from_page(pages, "market")
        risks = self._bullets_from_page(pages, "risk")
        recommendations = self._tail_bullets_from_page(pages, "strategy")

        output = ReportOutput(
            executive_summary=markdown,
            key_findings=[{"insight": item, "evidence_ids": []} for item in findings],
            risks=[{"insight": item, "evidence_ids": []} for item in risks],
            recommendations=[{"insight": item, "evidence_ids": []} for item in recommendations],
            confidence=max(0.0, critique["score"] - (0.05 * len(validation_issues))),
            evidence_gaps=coverage_gaps + validation_issues + critique["issues"],
            page_order=[page.page_id for page in pages],
            report_critique=critique,
        )
        return output.__dict__

    def _bullets_from_page(self, pages: List[GeneratedPage], page_id: str) -> list[str]:
        page = next((page for page in pages if page.page_id == page_id), None)
        if not page:
            return []
        return [line[2:].strip() for line in page.markdown.splitlines() if line.strip().startswith("- ")]

    def _tail_bullets_from_page(self, pages: List[GeneratedPage], page_id: str) -> list[str]:
        page = next((page for page in pages if page.page_id == page_id), None)
        if not page:
            return []
        body = page.markdown
        if "recommend" in body.lower():
            parts = re.split(r"(?im)^#+\s+.*recommend.*$", body)
            if len(parts) > 1:
                tail = parts[-1]
                bullets = [line[2:].strip() for line in tail.splitlines() if line.strip().startswith("- ")]
                if bullets:
                    return bullets
        return self._bullets_from_page(pages, page_id)
