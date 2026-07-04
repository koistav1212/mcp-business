import pytest

from services.research.critic_agent import CriticAgent
from services.research.industry_classifier import IndustryClassifier
from services.research.intent_engine import IntentEngine
from services.research.models import CitedInsight, DraftReport, EvidenceGraph, IntentPlan, ReportPlan, ReportSection, ResearchPlan
from services.host.host_agent import HostAgent
from services.research.report_planner import ReportPlanner
from services.research.research_planner import ResearchPlanner


@pytest.mark.asyncio
async def test_investment_query_selects_financial_providers_only():
    intent = await IntentEngine().extract("Analyze Tata Steel as a five-year investment", "Tata Steel")
    industry = IndustryClassifier().classify(intent)
    plan = ResearchPlanner().plan(intent, industry)

    assert intent.decision_type == "investment"
    assert industry.industry == "metals"
    assert {"company_provider", "news_provider", "sec_provider", "market_provider"} <= set(plan.providers)
    assert "people_provider" not in plan.providers
    assert "social_provider" not in plan.providers


@pytest.mark.asyncio
async def test_sales_query_drives_sales_evidence_and_report():
    context = await HostAgent().run("Sell TalentIQ to Zoho")

    assert context.get("research_plan").providers == ["company_provider", "news_provider", "people_provider", "technology_provider"]
    assert context.get("evidence_graph").nodes
    assert any(node.category == "hiring signals" for node in context.get("evidence_graph").nodes)
    assert [section.title for section in context.get("report_plan").sections][1:] == [
        "Company Priorities", "Leadership and Buying Group", "Hiring and Capability Signals", "Technology Fit", "Pursuit Recommendations"
    ]
    assert context.get("critique", {}).get("valid") is True


def test_report_plan_is_industry_specific():
    intent = IntentPlan(primary_goal="Analyze an investment in a bank", decision_type="investment", entities=["Example Bank"], confidence=0.9)
    industry = IndustryClassifier().classify(intent)
    plan = ReportPlanner().plan(intent, industry, EvidenceGraph())

    assert industry.industry == "banking"
    assert "Asset Quality and NPA" in [section.title for section in plan.sections]


def test_critic_rejects_unknown_evidence_ids():
    intent = IntentPlan(primary_goal="Analyze Acme", entities=["Acme"], confidence=0.9)
    research_plan = ResearchPlan()
    report_plan = ReportPlan(title="Acme", sections=[ReportSection(title="Summary", objective="Assess Acme")])
    draft = DraftReport(key_findings=[CitedInsight(insight="Revenue grew.", evidence_ids=["E-NOT-REAL"])])
    result = CriticAgent().review("Analyze Acme", intent, research_plan, EvidenceGraph(), report_plan, draft)

    assert result.valid is False
    assert "Unsupported evidence IDs" in result.issues[0]
