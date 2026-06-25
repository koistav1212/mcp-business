import pytest
from services.research.base import BaseProvider
from services.host.host_agent import HostAgent
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
    orchestrator = HostAgent()
    context = await orchestrator.run("Research Zoho")

    assert isinstance(context, dict)
    
    # 1. Company profile verification
    profile = context.get("profile", {})
    assert profile.get("name") == "Zoho Corporation"
    assert profile.get("employee_count", {}).get("value") == 12000
    assert profile.get("headquarters", {}).get("value") == "Chennai, India & Austin, Texas"
    
    # 2. Technology stack
    tech_stack = context.get("technology_stack", [])
    assert "React" in tech_stack
    assert "PostgreSQL" in tech_stack
    
    # 3. Leadership & Competitors
    leaders = [l.get("name") for l in context.get("leadership", [])]
    assert "Sridhar Vembu" in leaders
    assert "Radha Vembu" in leaders
    
    competitors = [c.get("name") for c in context.get("competitors", [])]
    assert "Salesforce" in competitors
    assert "HubSpot" in competitors

    # 4. News aggregation
    news_titles = [n.get("title") for n in context.get("news", [])]
    assert "Zoho launches new AI-driven CRM tools" in news_titles

    # 5. Hiring Signals
    signals = [s.get("role_title") for s in context.get("hiring_signals", [])]
    assert "Senior React Developer" in signals

    # 6. Source citation check
    assert len(context.get("sources", [])) >= 3

    # 7. Confidence & Timestamp metadata
    assert context.get("confidence_score", 0) > 0.5
    assert context.get("generated_at") is not None

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
    orchestrator = HostAgent()
    context = await orchestrator.run("AcmeCorp")

    profile = context.get("profile", {})
    assert profile.get("name") == "Acmecorp"
    assert profile.get("employee_count", {}).get("value") == 100
    assert profile.get("headquarters", {}).get("value") == "Unknown"
    
    assert context.get("confidence_score", 1.0) <= 0.6

@pytest.mark.asyncio
async def test_real_data_provider_nvidia():
    orchestrator = HostAgent()
    context = await orchestrator.run("Research Nvidia")

    assert isinstance(context, dict)
    
    # 1. Company profile verification from Wikipedia/yfinance
    profile = context.get("profile", {})
    assert "Nvidia" in profile.get("name", "") or "NVIDIA" in profile.get("name", "")
    assert "Santa Clara" in profile.get("headquarters", {}).get("value", "") or "California" in profile.get("headquarters", {}).get("value", "")
    assert profile.get("employee_count", {}).get("value", 0) > 1000
    assert "nvidia.com" in profile.get("website", "")
    assert "Jensen Huang" in profile.get("founders", [])
    
    # 2. Financials from yfinance/sec
    financials = context.get("financials", {})
    assert financials is not None
    assert financials.get("market_cap", 0) > 100_000_000_000 # Nvidia market cap is > $100B
    assert len(financials.get("revenue_history", {})) > 0
    assert len(financials.get("net_income_history", {})) > 0
    assert len(financials.get("assets_history", {})) > 0
    assert len(financials.get("liabilities_history", {})) > 0
    assert len(financials.get("cash_flow_history", {})) > 0

    # 3. News aggregation
    news = context.get("news", [])
    assert len(news) > 0
    news_types = [n.get("type") for n in news]
    assert any(nt in ["product_launch", "earnings", "litigation", "acquisition", "investment", "leadership_change", "general"] for nt in news_types)

    # 4. Raw data storage
    raw_data = context.get("raw_data", {})
    assert "company" in raw_data
    assert "financials" in raw_data
    assert "news" in raw_data
    assert "market_data" in raw_data
    assert "cik" in raw_data.get("financials", {})
    assert "ticker" in raw_data.get("market_data", {})

@pytest.mark.asyncio
async def test_confidence_gate_rejection():
    orchestrator = HostAgent()
    # Misspelled company that won't resolve with high confidence
    result = await orchestrator.run("Nivdia deep analysis")
    
    assert isinstance(result, dict)
    assert result["status"] == "needs_clarification"
    assert result["query"] == "Nivdia deep analysis"
    assert len(result["closest_candidates"]) > 0
    assert any("NVIDIA" in c["name"] for c in result["closest_candidates"])

@pytest.mark.asyncio
async def test_dynamic_intent_filtering_financial_only():
    orchestrator = HostAgent()
    # Ask explicitly for financial history only
    context = await orchestrator.run("Get Zoho's financial history and stock valuation details only")
    
    assert isinstance(context, dict)
    # Financials should exist
    assert context.get("financials") is not None
    assert context.get("technology_stack") is None
    assert context.get("hiring_signals") is None
    assert context.get("leadership") is None
    assert context.get("news") is None


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

