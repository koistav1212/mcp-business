import json
import logging
from typing import Optional

from services.llm.provider_router import ProviderRouter
from services.planning.models import ExecutionPlan, ResearchTask, Priority
from services.planning.planner_prompts import PLANNER_SYSTEM_PROMPT
from services.planning.planner_validator import PlannerValidator
from services.planning.token_estimator import TokenEstimator
from services.planning.task_scheduler import TaskScheduler

logger = logging.getLogger("uvicorn.error")

class PlannerAgent:
    async def execute(self, user_query: str) -> ExecutionPlan:
        """
        Translates a user request into a complete Consulting Execution Plan (WBS).
        """
        if True:
            try:
                planner_input = {
                    "user_query": user_query,
                    "entities": [user_query.strip()[:50]],
                    "intent": "comprehensive_research",
                    "workspace": "mcp-business",
                    "available_tools": ["sec_data", "market_data", "news_feed", "company_profile", "social_sentiment", "technology_stack", "people_data", "web_search"],
                    "available_agents": ["financial_agent", "competitor_agent", "industry_agent", "news_agent", "technology_agent", "risk_agent", "valuation_agent", "growth_agent", "ai_agent", "mna_agent", "entity_extractor"]
                }
                
                payload = await ProviderRouter.generate_json(
                    agent_name="planner",
                    system_prompt=PLANNER_SYSTEM_PROMPT,
                    user_prompt=json.dumps(planner_input)
                )
                
                # Parse to ExecutionPlan
                plan = ExecutionPlan.model_validate(payload)
                
                # Validate the graph and requirements
                if PlannerValidator.validate(plan):
                    # Estimate tokens and costs
                    plan = TokenEstimator.estimate(plan)
                    
                    # Schedule into execution waves
                    plan = TaskScheduler.schedule(plan)
                    return plan
                else:
                    logger.error("LLM generated an invalid execution plan structure.")
                    
            except Exception as e:
                logger.error(f"LLM planner failed: {e}. Falling back to basic WBS.")
                
        return self._generate_fallback_plan(user_query)
        
    def _generate_fallback_plan(self, user_query: str) -> ExecutionPlan:
        """
        Hardcoded WBS DAG fallback in case LLM generation fails or validation fails.
        """
        company_name = user_query.replace("Research ", "").strip()[:50]
        
        # ENT-001: Entity Resolution
        ent_task = ResearchTask(
            task_id="ENT-001",
            title="Entity Resolution",
            description="Extract and canonicalize company names and tickers.",
            objective="Ensure downstream tasks query the correct entities.",
            owner_agent="entity_extractor",
            priority=Priority.CRITICAL,
            dependencies=[],
            expected_output="EntityResolution",
            estimated_tokens=500
        )
        
        # FIN-001: Financial Retrieval
        fin_task = ResearchTask(
            task_id="FIN-001",
            title="Financial Benchmarking",
            description="Retrieve revenue and margins.",
            objective="Analyze basic financial performance.",
            owner_agent="financial_agent",
            required_sources=["sec_data", "market_data"],
            priority=Priority.HIGH,
            dependencies=["ENT-001"],
            expected_output="FinancialEvidence",
            estimated_tokens=1500
        )
        
        # COMP-001: Competitor Retrieval
        comp_task = ResearchTask(
            task_id="COMP-001",
            title="Competitor Landscape",
            description="Identify primary competitors.",
            objective="Understand market positioning.",
            owner_agent="competitor_agent",
            required_sources=["company_profile"],
            priority=Priority.HIGH,
            dependencies=["ENT-001"],
            expected_output="CompanyEvidence",
            estimated_tokens=1000
        )
        
        plan = ExecutionPlan(
            execution_id="fallback_001",
            research_objective="Basic fallback analysis",
            company=company_name,
            research_tasks=[ent_task, fin_task, comp_task]
        )
        
        plan = TokenEstimator.estimate(plan)
        return TaskScheduler.schedule(plan)
