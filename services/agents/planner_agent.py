import json
import logging
import re
from typing import Any, Dict, List, Optional

from services.core.models import AnalysisDepth, ExecutionWave, Priority, ResearchExecutionPlan, ResearchTask, ResearchType
from services.llm.provider_router import ProviderRouter
from services.planning.planner_prompts import build_planner_system_prompt
from services.schemas.insight import EntityResolution, LightweightPlannerOutput

logger = logging.getLogger("uvicorn.error")

PROVIDER_MAP = {
    "sec": "sec_edgar",
    "company": "company_provider",
    "news": "news_provider",
    "reddit": "reddit_provider",
    "hiring": "people_provider",
    "market": "yfinance",
    "web": "web_provider",
    "products": "web_provider",
    "patents": "web_provider",
}

def _target_field_for_provider(provider_name: str, company_entity: Optional[EntityResolution] = None) -> str:
    if provider_name in {"market_provider", "yfinance", "global_markets"}:
        return "ticker"
    if provider_name in {"sec_provider", "sec_edgar"}:
        return "cik"
    if provider_name == "web_provider":
        return "web_target" if company_entity and company_entity.website else "canonical_name"
    return "canonical_name"


class PlannerAgent:
    """
    Lightweight, metadata-driven planner agent.
    Decides required evidence, selected providers, required sections, and priority.
    """

    async def execute(self, user_query: str, company_entity: Any = None) -> ResearchExecutionPlan:
        # Build the new metadata context
        entity_name = getattr(company_entity, "company", getattr(company_entity, "company_name", None)) or user_query
        
        metadata = {
            "query": user_query,
            "entity": {
                "name": entity_name,
                "ticker": getattr(company_entity, "ticker", None),
                "cik": getattr(company_entity, "cik", None),
                "website": getattr(company_entity, "website", None),
            },
            "workspace_type": "company",
            "research_depth": "deep",
            "available_providers": list(PROVIDER_MAP.keys()),
            "provider_capabilities": {},
            "available_widgets": [],
            "user_intent": "CEO Intelligence"
        }

        try:
            payload = await ProviderRouter.generate_json(
                agent_name="planner",
                system_prompt=build_planner_system_prompt(),
                user_prompt=json.dumps(metadata, default=str),
            )

            # Validate against LightweightPlannerOutput
            planner_output = LightweightPlannerOutput.model_validate(payload)
        except Exception as exc:
            logger.error(f"PlannerAgent LLM execution failed: {exc}. Falling back to default plan.")
            planner_output = LightweightPlannerOutput(
                required_evidence=["company overview", "financial reports", "recent news"],
                selected_providers=["company", "sec", "news"],
                required_sections=["Financials", "Competitor Intelligence", "News and Risk Intelligence"],
                priority="medium",
                reasoning=["Fallback default plan due to error."]
            )

        # Force inclusion of vital providers for complete coverage
        forced_providers = {"market", "web", "reddit", "company", "news", "sec"}
        for fp in forced_providers:
            if fp not in planner_output.selected_providers:
                planner_output.selected_providers.append(fp)

        # Map to ResearchExecutionPlan for scheduler compatibility
        tasks = []
        required_providers = []
        for index, p_name in enumerate(planner_output.selected_providers):
            mapped_p = PROVIDER_MAP.get(p_name, p_name)
            required_providers.append(mapped_p)
            tasks.append(
                ResearchTask(
                    task_id=f"{mapped_p}_{index}",
                    provider_name=mapped_p,
                    target_field=_target_field_for_provider(mapped_p, company_entity),
                    priority=Priority.MEDIUM,
                    timeout_seconds=180.0,
                    max_retries=2,
                )
            )

        execution_waves = []
        if tasks:
            execution_waves.append(
                ExecutionWave(
                    wave_number=1,
                    name="Wave 1: Data Gathering",
                    tasks=tasks,
                    is_mandatory=True,
                    stop_on_failure=False,
                )
            )

        plan = ResearchExecutionPlan(
            plan_id="plan_" + re.sub(r"\W+", "_", entity_name.lower())[:15],
            goal=user_query,
            intent="CEO Intelligence",
            research_type=ResearchType.COMPANY_DEEP_DIVE,
            decision_type="strategy",
            workspace_type="CEO_REPORT",
            primary_entity_query=entity_name,
            execution_waves=execution_waves,
            required_providers=list(dict.fromkeys(required_providers)),
            optional_providers=[],
            required_domains=planner_output.selected_providers,
            analysis_depth=AnalysisDepth.DEEP,
            planner_reasoning=planner_output.reasoning,
        )

        # Store selected sections, required evidence, and priority in dynamic metadata field of plan
        plan.metadata = {
            "required_evidence": planner_output.required_evidence,
            "required_sections": planner_output.required_sections,
            "priority": planner_output.priority,
        }

        # Write to artifact for pipeline debugging
        from services.artifacts.artifact_writer import ArtifactWriter
        ArtifactWriter.write_json(
            "research_execution_plan.json",
            {
                "planner_context": metadata,
                "planner_payload": planner_output.model_dump(),
                "plan_summary": plan.to_summary() if hasattr(plan, "to_summary") else str(plan),
            },
        )

        return plan
