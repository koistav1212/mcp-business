import pytest
from services.research.base import BaseProvider
from services.research.orchestrator import ResearchOrchestrator
from services.research.models import ResearchContext, Source
from services.research.providers.company_provider import CompanyProvider
from services.research.providers.web_provider import WebProvider
from services.research.providers.news_provider import NewsProvider
from services.research.providers.yfinance_provider import YFinanceProvider
from services.research.providers.sec_edgar_provider import SECEdgarProvider
from services.research.providers.people_provider import PeopleProvider
from services.research.providers.reddit_provider import RedditProvider

def test_provider_inheritance():
    # Verify that all providers subclass BaseProvider contract
    assert issubclass(CompanyProvider, BaseProvider)
    assert issubclass(WebProvider, BaseProvider)
    assert issubclass(NewsProvider, BaseProvider)
    assert issubclass(YFinanceProvider, BaseProvider)
    assert issubclass(SECEdgarProvider, BaseProvider)
    assert issubclass(PeopleProvider, BaseProvider)
    assert issubclass(RedditProvider, BaseProvider)

@pytest.mark.asyncio
async def test_orchestrator_zoho_success():
    orchestrator = ResearchOrchestrator()
    context = await orchestrator.run("Zoho")

    assert isinstance(context, ResearchContext)
    
    # 1. Company profile verification
    assert context.profile.name == "Zoho Corporation"
    assert context.profile.employee_count.value == 12000
    assert context.profile.headquarters.value == "Chennai, India & Austin, Texas"
    
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

    # 7. Confidence & Timestamp metadata
    assert context.confidence_score > 0.5
    assert context.generated_at is not None

@pytest.mark.asyncio
async def test_conflict_detection_and_resolution():
    from services.research.synthesizer import ResearchSynthesizer
    from services.research.models import RawResearchBundle, EntityResolution
    
    synthesizer = ResearchSynthesizer()
    
    # Setup a bundle with conflicting financial reports
    bundle = RawResearchBundle(
        company_raw={"name": "Test Company", "source_title": "Source A", "source_url": "url A", "source_type": "official_website"},
        web_raw={"technology_stack": []},
        news_raw={"news": []},
        financial_raw={
            "financial_reports": [
                {
                    "source_title": "Forbes Business Profiles",
                    "source_url": "https://forbes.com",
                    "source_type": "commercial_database",
                    "revenue_annual": "$1.0B"
                },
                {
                    "source_title": "Crunchbase Corporate Profile",
                    "source_url": "https://crunchbase.com",
                    "source_type": "commercial_database",
                    "revenue_annual": "$1.2B"
                }
            ]
        },
        people_raw={"leadership": []}
    )
    
    entity = EntityResolution(company_name="Test Company", confidence=1.0)
    context = await synthesizer.synthesize(
        bundle=bundle,
        entity=entity,
        sec_data={"revenue_history": {}, "raw_data": {}},
        yf_data={"raw_data": {}},
        reddit_data={}
    )
    
    assert len(context.conflicts) >= 1
    assert "Conflict: Revenue figures mismatch" in context.conflicts[0]
    assert context.financials is not None
    assert context.financials.revenue_annual in ["$1.0B", "$1.2B"]

@pytest.mark.asyncio
async def test_orchestrator_generic_fallback():
    orchestrator = ResearchOrchestrator()
    context = await orchestrator.run("AcmeCorp")

    assert context.profile.name == "Acmecorp"
    assert context.profile.employee_count.value == 100
    assert context.profile.headquarters.value == "Unknown"
    
    assert context.confidence_score <= 0.6

@pytest.mark.asyncio
async def test_real_data_provider_nvidia():
    orchestrator = ResearchOrchestrator()
    context = await orchestrator.run("Nvidia")

    assert isinstance(context, ResearchContext)
    
    # 1. Company profile verification from Wikipedia/yfinance
    assert "Nvidia" in context.profile.name or "NVIDIA" in context.profile.name
    assert "Santa Clara" in context.profile.headquarters.value or "California" in context.profile.headquarters.value
    assert context.profile.employee_count.value > 1000
    assert "nvidia.com" in context.profile.website
    assert "Jensen Huang" in context.profile.founders
    
    # 2. Financials from yfinance/sec
    assert context.financials is not None
    assert context.financials.market_cap > 100_000_000_000 # Nvidia market cap is > $100B
    assert len(context.financials.revenue_history) > 0
    assert len(context.financials.net_income_history) > 0
    assert len(context.financials.assets_history) > 0
    assert len(context.financials.liabilities_history) > 0
    assert len(context.financials.cash_flow_history) > 0

    # 3. News aggregation
    assert len(context.news) > 0
    news_types = [n.type for n in context.news]
    assert any(nt in ["product_launch", "earnings", "litigation", "acquisition", "investment", "leadership_change", "general"] for nt in news_types)

    # 4. Raw data storage
    assert "company" in context.raw_data
    assert "financials" in context.raw_data
    assert "news" in context.raw_data
    assert "market_data" in context.raw_data
    assert "cik" in context.raw_data["financials"]
    assert "ticker" in context.raw_data["market_data"]

@pytest.mark.asyncio
async def test_confidence_gate_rejection():
    orchestrator = ResearchOrchestrator()
    # Misspelled company that won't resolve with high confidence
    result = await orchestrator.run("Nivdia deep analysis")
    
    assert isinstance(result, dict)
    assert result["status"] == "needs_clarification"
    assert result["query"] == "Nivdia deep analysis"
    assert len(result["closest_candidates"]) > 0
    assert any("NVIDIA" in c["name"] for c in result["closest_candidates"])

@pytest.mark.asyncio
async def test_dynamic_intent_filtering_financial_only():
    orchestrator = ResearchOrchestrator()
    # Ask explicitly for financial history only
    context = await orchestrator.run("Zoho", user_query="Get Zoho's financial history and stock valuation details only")
    
    assert isinstance(context, ResearchContext)
    # Financials should exist
    assert context.financials is not None
    assert context.technology_stack is None
    assert context.hiring_signals is None
    assert context.leadership is None
    assert context.news is None


def test_no_hardcoded_company_branches():
    import os
    research_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for root, dirs, files in os.walk(research_dir):
        # Exclude the tests directory
        if "tests" in root.split(os.sep):
            continue
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                lines = content.splitlines()
                for line_idx, line in enumerate(lines, 1):
                    line_lower = line.lower()
                    if "zoho" in line_lower:
                        raise AssertionError(f"Found forbidden substring 'zoho' in {path}:{line_idx}: {line.strip()}")
                    if "acme" in line_lower:
                        raise AssertionError(f"Found forbidden substring 'acme' in {path}:{line_idx}: {line.strip()}")
                    if ".mock" in line_lower:
                        raise AssertionError(f"Found forbidden substring '.MOCK' in {path}:{line_idx}: {line.strip()}")
                    if '"note":' in line and "mocked" in line_lower:
                        raise AssertionError(f"Found forbidden pattern '\"note\":' + 'Mocked' in {path}:{line_idx}: {line.strip()}")

