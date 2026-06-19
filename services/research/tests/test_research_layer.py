import pytest
from services.research.base import BaseProvider
from services.research.orchestrator import ResearchOrchestrator
from services.research.models import ResearchContext, Source
from services.research.providers.company_provider import CompanyProvider
from services.research.providers.web_provider import WebProvider
from services.research.providers.news_provider import NewsProvider
from services.research.providers.financial_provider import FinancialProvider
from services.research.providers.people_provider import PeopleProvider

def test_provider_inheritance():
    # Verify that all providers subclass BaseProvider contract
    assert issubclass(CompanyProvider, BaseProvider)
    assert issubclass(WebProvider, BaseProvider)
    assert issubclass(NewsProvider, BaseProvider)
    assert issubclass(FinancialProvider, BaseProvider)
    assert issubclass(PeopleProvider, BaseProvider)

@pytest.mark.asyncio
async def test_orchestrator_zoho_success():
    orchestrator = ResearchOrchestrator()
    context = await orchestrator.run("Zoho")

    assert isinstance(context, ResearchContext)
    
    # 1. Company profile verification
    assert context.company_profile.name == "Zoho Corporation"
    assert context.company_profile.employee_count == 12000
    assert context.company_profile.headquarters == "Chennai, India & Austin, Texas"
    
    # 2. Technology stack
    assert "React" in context.technology_stack
    assert "PostgreSQL" in context.technology_stack
    
    # 3. Leadership & Competitors
    leaders = [l.name for l in context.leadership]
    assert "Sridhar Vembu" in leaders
    assert "Radha Vembu" in leaders
    
    competitors = [c.name for c in context.competitors]
    assert "Salesforce" in competitors
    assert "HubSpot" in competitors

    # 4. News aggregation
    news_titles = [n.title for n in context.news]
    assert "Zoho launches new AI-driven CRM tools" in news_titles

    # 5. Hiring Signals
    signals = [s.role_title for s in context.hiring_signals]
    assert "Senior React Developer" in signals

    # 6. Source citation check
    assert len(context.sources) >= 3
    source_urls = [s.url for s in context.sources]
    assert "https://builtwith.com/zoho.com" in source_urls
    assert "https://linkedin.com/company/zoho" in source_urls

    # 7. Confidence & Timestamp metadata
    assert context.confidence_score > 0.5
    assert context.generated_at is not None

@pytest.mark.asyncio
async def test_conflict_detection_and_resolution():
    orchestrator = ResearchOrchestrator()
    context = await orchestrator.run("Zoho")

    # Mismatch was introduced in financial_provider between Forbes ($1.0B) and Crunchbase ($1.2B)
    assert len(context.conflicts) >= 1
    assert "Conflict: Revenue figures mismatch" in context.conflicts[0]
    
    # Check that a resolved financial profile is still built
    assert context.financials is not None
    assert context.financials.revenue_annual in ["$1.0B", "$1.2B"]

@pytest.mark.asyncio
async def test_orchestrator_generic_fallback():
    orchestrator = ResearchOrchestrator()
    context = await orchestrator.run("AcmeCorp")

    assert context.company_profile.name == "Acmecorp"
    assert context.company_profile.employee_count == 100
    assert context.company_profile.headquarters == "Unknown"
    
    # Fallback uses lower quality sources (directories), confidence score should reflect this
    assert context.confidence_score <= 0.6
