import json
import logging
from typing import Dict, Any

from services.llm.provider_router import ProviderRouter
from services.models.research_execution_plan import (
    ResearchExecutionPlan, ResearchType, AnalysisDepth, Priority,
    ExecutionWave, ResearchTask, DependencyEdge, StopCondition
)
from services.planning.planner_prompts import PLANNER_SYSTEM_PROMPT

logger = logging.getLogger("uvicorn.error")

def parse_execution_plan(data: Dict[str, Any]) -> ResearchExecutionPlan:
    """
    Parses a raw JSON dictionary into the structured ResearchExecutionPlan dataclass.
    """
    waves = []
    for wave_data in data.get("execution_waves", []):
        tasks = []
        for task_data in wave_data.get("tasks", []):
            task = ResearchTask(
                task_id=task_data.get("task_id", ""),
                provider_name=task_data.get("provider_name", ""),
                target_field=task_data.get("target_field", "canonical_name"),
                priority=Priority(task_data.get("priority", Priority.MEDIUM.value)),
                timeout_seconds=task_data.get("timeout_seconds", 30.0),
                max_retries=task_data.get("max_retries", 2),
                dependencies=task_data.get("dependencies", []),
                fallback_provider=task_data.get("fallback_provider"),
                consuming_agents=task_data.get("consuming_agents", []),
                estimated_latency_ms=task_data.get("estimated_latency_ms", 5000),
                estimated_tokens=task_data.get("estimated_tokens", 200),
                cost_signal=task_data.get("cost_signal", "free")
            )
            tasks.append(task)
            
        wave = ExecutionWave(
            wave_number=wave_data.get("wave_number", 1),
            name=wave_data.get("name", "Unknown Wave"),
            tasks=tasks,
            is_mandatory=wave_data.get("is_mandatory", True),
            stop_on_failure=wave_data.get("stop_on_failure", False)
        )
        waves.append(wave)

    dependencies = []
    for dep_data in data.get("dependency_graph", []):
        dep = DependencyEdge(
            from_task=dep_data.get("from_task", ""),
            to_task=dep_data.get("to_task", ""),
            dependency_type=dep_data.get("dependency_type", "data"),
            reason=dep_data.get("reason", "")
        )
        dependencies.append(dep)

    stops = []
    for stop_data in data.get("stop_conditions", []):
        stop = StopCondition(
            condition_type=stop_data.get("condition_type", ""),
            threshold=stop_data.get("threshold", 0.0),
            action=stop_data.get("action", "skip_optional")
        )
        stops.append(stop)

    return ResearchExecutionPlan(
        plan_id=data.get("plan_id", "plan_001"),
        goal=data.get("goal", ""),
        intent=data.get("intent", ""),
        research_type=ResearchType(data.get("research_type", ResearchType.COMPANY_DEEP_DIVE.value)),
        decision_type=data.get("decision_type", "informational"),
        workspace_type=data.get("workspace_type", "GENERAL"),
        primary_entity_query=data.get("primary_entity_query", ""),
        comparison_entity_queries=data.get("comparison_entity_queries", []),
        entity_confidence_threshold=data.get("entity_confidence_threshold", 0.55),
        execution_waves=waves,
        dependency_graph=dependencies,
        required_providers=data.get("required_providers", []),
        optional_providers=data.get("optional_providers", []),
        required_domains=data.get("required_domains", []),
        agent_dependencies=data.get("agent_dependencies", {}),
        analysis_depth=AnalysisDepth(data.get("analysis_depth", AnalysisDepth.STANDARD.value)),
        max_execution_seconds=data.get("max_execution_seconds", 90.0),
        max_total_tokens=data.get("max_total_tokens", 12000),
        estimated_cost=data.get("estimated_cost", "free"),
        stop_conditions=stops,
        success_criteria=data.get("success_criteria", []),
        minimum_evidence_coverage=data.get("minimum_evidence_coverage", 0.60),
        required_data=data.get("required_data", []),
        max_research_iterations=data.get("max_research_iterations", 1),
        created_at=data.get("created_at", ""),
        planner_reasoning=data.get("planner_reasoning", [])
    )

class PlannerAgent:
    """
    The Brain of the system.
    Determines required domains and builds a complete ResearchExecutionPlan.
    """
    async def execute(self, user_query: str) -> ResearchExecutionPlan:
        try:
            planner_input = {
                "user_query": user_query,
                "intent": "comprehensive_research",
                "workspace": "mcp-business",
                "available_domains": ["financial_history", "market_data", "news", "leadership"]
            }
            
            payload = await ProviderRouter.generate_json(
                agent_name="planner",
                system_prompt=PLANNER_SYSTEM_PROMPT,
                user_prompt=json.dumps(planner_input)
            )
            
            plan = parse_execution_plan(payload)
            
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
            task_id="FIN-001",
            provider_name="sec_provider",
            target_field="ticker",
            priority=Priority.HIGH
        )
        
        wave1 = ExecutionWave(
            wave_number=1,
            name="Wave 1: Financials",
            tasks=[task1]
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
