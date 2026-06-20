import pytest
from services.planning.goal_extractor import GoalExtractor
from services.planning.framework_selector import FrameworkSelector, FrameworkType
from services.planning.planner import PromptUnderstandingAgent, PromptPlan
from services.planning.research_planner import DynamicResearchPlanner
from services.research.models import (
    FinancialResearchContext,
    SalesResearchContext,
    HiringResearchContext,
    CompetitiveResearchContext,
    ResearchContext,
    CompanyProfile,
    FinancialData
)

# A mock JSON generator that simulates LLM response
async def mock_json_generator(system_prompt: str, user_prompt: str) -> dict:
    if "zoho" in user_prompt.lower():
        # check system prompt to decide what model to return
        if "Goal Extraction" in system_prompt:
            return {
                "primary_goal": "sales",
                "user_problem": "Pitch TalentIQ to Zoho stakeholders",
                "desired_output": "sales_strategy",
                "decision_type": "account_based_selling"
            }
        elif "Report Framework Selector" in system_prompt:
            return {
                "framework": "SALES_PLAYBOOK",
                "rationale": "Matches sales pitch criteria"
            }
        else:
            return {
                "target_company": "Zoho",
                "intent": "sales_strategy",
                "research_goal": "Pitch TalentIQ AI Interview Platform to Zoho stakeholders",
                "industry": "saas",
                "time_horizon": "current",
                "required_sources": ["company", "people", "hiring", "competitors", "news"],
                "required_analytics": ["buyer_mapping", "pain_points", "hiring_trends", "competitive_position"],
                "report_framework": "sales_account_plan"
            }
    elif "nvidia" in user_prompt.lower():
        if "Goal Extraction" in system_prompt:
            return {
                "primary_goal": "investment",
                "user_problem": "Evaluate NVIDIA stock valuation and risks",
                "desired_output": "equity_research",
                "decision_type": "stock_investment"
            }
        elif "Report Framework Selector" in system_prompt:
            return {
                "framework": "EQUITY_RESEARCH",
                "rationale": "Matches investment analysis criteria"
            }
        else:
            return {
                "target_company": "NVIDIA",
                "intent": "investment_analysis",
                "research_goal": "Evaluate whether NVIDIA is an attractive investment today",
                "industry": "semiconductor",
                "time_horizon": "10_years",
                "required_sources": ["sec", "yfinance", "news", "reddit"],
                "required_analytics": ["revenue_growth", "earnings_growth", "valuation", "risk_analysis"],
                "report_framework": "equity_research"
            }
    return {}

@pytest.mark.anyio
async def test_goal_extractor():
    extractor = GoalExtractor(json_generator=mock_json_generator)
    goal = await extractor.extract("Sell TalentIQ to Zoho")
    assert goal.primary_goal == "sales"
    assert goal.desired_output == "sales_strategy"
    assert goal.decision_type == "account_based_selling"

@pytest.mark.anyio
async def test_framework_selector():
    selector = FrameworkSelector(json_generator=mock_json_generator)
    sel = await selector.select("investment_analysis", {"prompt": "Should I invest in NVIDIA today?"})
    assert sel.framework == FrameworkType.EQUITY_RESEARCH
    
    # Test heuristic fallback
    selector_heur = FrameworkSelector(json_generator=None)
    sel_heur = await selector_heur.select("sales_strategy")
    assert sel_heur.framework == FrameworkType.SALES_PLAYBOOK

@pytest.mark.anyio
async def test_prompt_understanding_agent_llm():
    agent = PromptUnderstandingAgent(json_generator=mock_json_generator)
    
    # Test case 1: Sell TalentIQ to Zoho
    res_zoho = await agent.plan("Sell TalentIQ to Zoho")
    assert res_zoho["target_company"] == "Zoho"
    assert res_zoho["intent"] == "sales_strategy"
    assert res_zoho["industry"] == "saas"
    assert "company" in res_zoho["required_sources"]
    assert "buyer_mapping" in res_zoho["required_analytics"]
    assert res_zoho["report_framework"] == "sales_account_plan"
    
    # Test case 2: Should I invest in NVIDIA today?
    res_nvidia = await agent.plan("Should I invest in NVIDIA today?")
    assert res_nvidia["target_company"] == "NVIDIA"
    assert res_nvidia["intent"] == "investment_analysis"
    assert "sec" in res_nvidia["required_sources"]
    assert "valuation" in res_nvidia["required_analytics"]
    assert res_nvidia["report_framework"] == "equity_research"

@pytest.mark.anyio
async def test_prompt_understanding_agent_heuristic():
    agent = PromptUnderstandingAgent(json_generator=None)
    
    # Test sales heuristic
    res_zoho = await agent.plan("Sell TalentIQ to Zoho")
    assert res_zoho["target_company"] == "Zoho"
    assert res_zoho["intent"] == "sales_strategy"
    
    # Test financial 10 years heuristic
    res_nvidia_10y = await agent.plan("Analyze NVIDIA's financial performance over the last 10 years")
    assert res_nvidia_10y["target_company"] == "NVIDIA"
    assert res_nvidia_10y["intent"] == "financial_analysis"
    assert "sec" in res_nvidia_10y["required_sources"]
    assert res_nvidia_10y["time_horizon"] == "10_years"


@pytest.mark.anyio
async def test_stock_query_preserves_named_company_when_llm_generalizes_it():
    async def hallucinating_generator(system_prompt: str, user_prompt: str) -> dict:
        return {
            "target_company": "Big Tech",
            "intent": "general",
            "research_goal": "Review the technology sector",
            "industry": "technology",
            "time_horizon": "current",
            "required_sources": ["news"],
            "required_analytics": [],
            "report_framework": "general_brief",
        }

    result = await PromptUnderstandingAgent(json_generator=hallucinating_generator).plan("APple Stocks")

    assert result["target_company"].lower() == "apple"
    assert result["intent"] == "investment_analysis"
    assert {"company", "sec", "yfinance", "news"} <= set(result["required_sources"])
    assert result["report_framework"] == "equity_research"

def test_dynamic_research_planner():
    planner = DynamicResearchPlanner()
    
    # Query 1 sources plan
    plan_1 = planner.plan({
        "intent": "financial_analysis",
        "required_sources": ["sec", "yfinance", "news"]
    })
    assert {"task": "financial_history", "provider": "sec"} in plan_1
    assert {"task": "market_valuation", "provider": "yfinance"} in plan_1
    assert {"task": "recent_developments", "provider": "news"} in plan_1
    
    # Query 2 sources plan
    plan_2 = planner.plan({
        "intent": "sales_strategy",
        "required_sources": ["company", "people", "hiring", "news"]
    })
    assert {"task": "company_profile", "provider": "company"} in plan_2
    assert {"task": "leadership", "provider": "people"} in plan_2
    assert {"task": "hiring_signals", "provider": "people"} in plan_2

def test_specialized_contexts():
    # Verify specialized research context fields
    profile = CompanyProfile(name="NVIDIA", overview="Chips", website="nvidia.com")
    financials = FinancialData(revenue_annual="$26B")
    
    ctx = ResearchContext(
        profile=profile,
        financials=financials,
        technology_stack=["CUDA", "C++"]
    )
    
    assert ctx.profile.name == "NVIDIA"
    assert ctx.financials.revenue_annual == "$26B"
    assert ctx.technology_stack == ["CUDA", "C++"]
    assert isinstance(ctx, FinancialResearchContext)
    assert isinstance(ctx, SalesResearchContext)
    assert isinstance(ctx, HiringResearchContext)
    assert isinstance(ctx, CompetitiveResearchContext)
