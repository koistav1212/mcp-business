import logging
from typing import Any, Dict, Optional

from services.research.models import ResearchContext

from .planning.data_profiler import DataProfiler
from .planning.insight_planner import InsightPlanner
from .planning.component_planner import ComponentPlanner
from .planning.page_composer import PageComposer
from .planning.ui_validator import UIValidator
from .schemas.ui_schema import UISchema

logger = logging.getLogger("uvicorn.error")

class UIAgent:
    """
    Executive Intelligence UI Orchestrator.
    Executes a 5-step process to generate an insight-driven UI schema.
    """
    def __init__(self, model_router=None):
        self.router = model_router
        self.data_profiler = DataProfiler()
        self.insight_planner = InsightPlanner(self.router)
        self.component_planner = ComponentPlanner(self.router)
        self.page_composer = PageComposer()
        self.validator = UIValidator()

    async def execute(
        self,
        context_or_query: ResearchContext | Dict[str, Any] | str,
        context_dict: Optional[Dict[str, Any]] = None,
    ) -> UISchema:
        """
        Orchestrates the UI generation.
        """
        context = self._coerce_context(context_or_query, context_dict)
        logger.info("Starting UI generation orchestration")

        # STEP 1: Data Profiling
        data_profile = self.data_profiler.profile(context)
        logger.info(f"Data Profile completed: {data_profile}")

        # STEP 2: Insight Planning
        insight_plan = await self.insight_planner.plan(
            context=context,
            data_profile=data_profile
        )
        logger.info(f"Insight Plan completed: {len(insight_plan.executive_questions)} questions")

        # STEP 3: Component Planning
        component_plan = await self.component_planner.plan(
            context=context,
            data_profile=data_profile,
            insight_plan=insight_plan
        )
        logger.info(f"Component Plan completed: {len(component_plan.selected_components)} components selected")

        # STEP 4: Page Composition
        ui_schema = self.page_composer.compose(
            context=context,
            data_profile=data_profile,
            insight_plan=insight_plan,
            component_plan=component_plan
        )

        # STEP 5: Validation
        validation = self.validator.validate(ui_schema, context)
        ui_schema.validation = validation
        
        if not validation.passed:
            logger.warning(
                "UI Validation failed: duplicates=%s nulls=%s raw_duplicates=%s biography=%s traceable=%s",
                validation.duplicate_components,
                validation.null_values_rendered,
                validation.raw_duplicate_products_rendered,
                validation.biography_style_detected,
                validation.all_claims_traceable,
            )
            # In a real scenario, we would trigger a self-correction loop here.

        return ui_schema

    def _coerce_context(
        self,
        context_or_query: ResearchContext | Dict[str, Any] | str,
        context_dict: Optional[Dict[str, Any]],
    ) -> ResearchContext:
        if isinstance(context_or_query, ResearchContext):
            return context_or_query
        if isinstance(context_or_query, dict):
            return ResearchContext.model_validate(context_or_query)
        if context_dict is None:
            raise ValueError("context_dict is required when execute() is called with a query string")
        return ResearchContext.model_validate(context_dict)
