import json
import logging
from typing import Dict, Any, Optional

from services.llm.provider_router import ProviderRouter
from services.models.research_execution_plan import (
    ResearchExecutionPlan, ResearchType, AnalysisDepth, Priority,
    ExecutionWave, ResearchTask, DependencyEdge, StopCondition
)
from services.research.models import EntityResolution
from services.planning.planner_prompts import PLANNER_SYSTEM_PROMPT
from services.planning.research_planner import DynamicResearchPlanner

logger = logging.getLogger("uvicorn.error")

def parse_execution_plan(data: Dict[str, Any], company_entity: Optional[EntityResolution] = None) -> ResearchExecutionPlan:
    """
    Parses a raw JSON dictionary into the structured ResearchExecutionPlan dataclass.
    """
    # Parse intent and required_sources from simplified JSON
    intent = data.get("intent", "comprehensive_research")
    required_sources = data.get("required_sources", [])
    
    # Use DynamicResearchPlanner to resolve tasks
    planner = DynamicResearchPlanner()
    mapped_tasks = planner.plan({"intent": intent, "required_sources": required_sources}, company_entity)
    
    tasks = []
    required_providers = []
    
    for i, t in enumerate(mapped_tasks):
        provider = t["provider"]
        required_providers.append(provider)
        
        target_field = "canonical_name"
        if provider in ["market_provider", "yfinance", "global_markets"]:
            target_field = "ticker"
        elif provider in ["sec_provider", "sec_edgar"]:
            target_field = "cik"
            
        tasks.append(ResearchTask(
            task_id=f"{provider}_{i}",
            provider_name=provider,
            target_field=target_field,
            priority=Priority.MEDIUM,
            timeout_seconds=30.0,
            max_retries=2
        ))
        
    wave = ExecutionWave(
        wave_number=1,
        name="Wave 1: Data Gathering",
        tasks=tasks,
        is_mandatory=True,
        stop_on_failure=False
    )

    return ResearchExecutionPlan(
        plan_id=data.get("plan_id", "plan_001"),
        goal=data.get("goal", ""),
        intent=intent,
        research_type=ResearchType(data.get("research_type", ResearchType.COMPANY_DEEP_DIVE.value)),
        decision_type=data.get("decision_type", "informational"),
        workspace_type=data.get("workspace_type", "GENERAL"),
        primary_entity_query=data.get("primary_entity_query", ""),
        execution_waves=[wave] if tasks else [],
        required_providers=list(set(required_providers)),
        required_domains=required_sources
    )

class PlannerAgent:
    """
    The Brain of the system.
    Determines required domains and builds a complete ResearchExecutionPlan.
    """
    async def execute(self, user_query: str, company_entity: Optional[EntityResolution] = None) -> ResearchExecutionPlan:
        try:
            planner_input = {
                "user_query": user_query,
                "intent": "comprehensive_research",
                "workspace": "mcp-business",
                "available_domains": ["financial_history", "market_data", "news", "leadership"]
            }
            
            payload_text = await ProviderRouter.generate_text(
                agent_name="planner",
                system_prompt=PLANNER_SYSTEM_PROMPT,
                user_prompt=json.dumps(planner_input)
            )
            
            from services.llm.provider_router import extract_json
            try:
                payload = extract_json(payload_text)
            except Exception:
                logger.warning("Could not extract JSON from planner text output. Falling back to basic WBS.")
                return self._generate_fallback_plan(user_query)
            
            plan = parse_execution_plan(payload, company_entity)
            
            from services.artifacts.artifact_writer import ArtifactWriter
            ArtifactWriter.write_json("research_execution_plan.json", payload)
            
            # Note: Planner no longer calls TaskScheduler.schedule(plan). 
            # The orchestrator will consume the plan separately.
            
            return plan
            
        except Exception as e:
            logger.error(f"LLM planner failed: {e}. Falling back to basic WBS.")
            return self._generate_fallback_plan(user_query)
            
    def _generate_fallback_plan(self, user_query: str) -> ResearchExecutionPlan:
        company_name = user_query.replace("Research ", "").strip()[:50]
        
        task1 = ResearchTask(
            task_id="CORE-001",
            provider_name="company_provider",
            target_field="canonical_name",
            priority=Priority.HIGH
        )
        task1b = ResearchTask(
            task_id="FIN-001",
            provider_name="yfinance",
            target_field="ticker",
            priority=Priority.HIGH
        )
        task2 = ResearchTask(
            task_id="CORE-002",
            provider_name="news_provider",
            target_field="query",
            priority=Priority.HIGH
        )
        task3 = ResearchTask(
            task_id="CORE-003",
            provider_name="web_provider",
            target_field="query",
            priority=Priority.HIGH
        )
        
        wave1 = ExecutionWave(
            wave_number=1,
            name="Wave 1: Core Research",
            tasks=[task1, task1b, task2, task3]
        )
        
        plan = ResearchExecutionPlan(
            plan_id="fallback_001",
            goal=user_query,
            intent="fallback",
            research_type=ResearchType.COMPANY_DEEP_DIVE,
            decision_type="informational",
            workspace_type="GENERAL",
            primary_entity_query=company_name,
            execution_waves=[wave1]
        )
        return plan
