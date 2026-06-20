import json
import logging
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, Optional
from pydantic import BaseModel

from services.research.json_llm import configured_json_generator

logger = logging.getLogger("uvicorn.error")

class FrameworkType(str, Enum):
    EQUITY_RESEARCH = "EQUITY_RESEARCH"
    SALES_PLAYBOOK = "SALES_PLAYBOOK"
    CONSULTING_REPORT = "CONSULTING_REPORT"
    MARKET_RESEARCH = "MARKET_RESEARCH"
    COMPETITIVE_INTELLIGENCE = "COMPETITIVE_INTELLIGENCE"
    DUE_DILIGENCE = "DUE_DILIGENCE"
    MNA_ANALYSIS = "MNA_ANALYSIS"
    TALENT_INTELLIGENCE = "TALENT_INTELLIGENCE"

class FrameworkSelection(BaseModel):
    framework: FrameworkType
    rationale: str

FRAMEWORK_SELECTOR_SYSTEM_PROMPT = f"""You are a Report Framework Selector.
Based on the intent, required analyses, and goals of a request, select the best matching framework.

Choose from the following FrameworkType values:
- {', '.join([f.value for f in FrameworkType])}

Your output must be JSON matching the schema:
{{
  "framework": "FrameworkType",
  "rationale": "A brief explanation of why this framework was chosen"
}}

Return ONLY the raw JSON object. Do not include markdown code block formatting (like ```json ... ```).
"""

class FrameworkSelector:
    """
    Selects the analytical and report framework structure based on research intent and details.
    """
    def __init__(self, json_generator: Optional[Callable[[str, str], Awaitable[Dict[str, Any]]]] = None):
        self.json_generator = json_generator or configured_json_generator()

    async def select(self, intent: str, goal_details: Optional[Dict[str, Any]] = None) -> FrameworkSelection:
        """
        Selects report framework.
        Uses OpenAIJSONGenerator if configured, otherwise falls back to heuristics.
        """
        if self.json_generator:
            try:
                payload = await self.json_generator(
                    FRAMEWORK_SELECTOR_SYSTEM_PROMPT,
                    json.dumps({"intent": intent, "goal_details": goal_details or {}})
                )
                return FrameworkSelection.model_validate(payload)
            except Exception as e:
                logger.warning(f"LLM framework selection failed: {e}. Falling back to heuristics.")

        return self._heuristic_select(intent, goal_details)

    def _heuristic_select(self, intent: str, goal_details: Optional[Dict[str, Any]]) -> FrameworkSelection:
        """
        Fallback heuristic selector.
        """
        intent_clean = intent.lower().strip()
        goal_str = str(goal_details or {}).lower()

        if "sales" in intent_clean or "sell" in goal_str or "sales_strategy" in intent_clean:
            return FrameworkSelection(
                framework=FrameworkType.SALES_PLAYBOOK,
                rationale="Selected Sales Playbook since the intent matches sales pitch and client strategy."
            )
        elif "investment" in intent_clean or "equity" in intent_clean or "valuation" in goal_str or "invest" in goal_str:
            return FrameworkSelection(
                framework=FrameworkType.EQUITY_RESEARCH,
                rationale="Selected Equity Research for financial performance evaluation and stock analysis."
            )
        elif "competitor" in intent_clean or "competitive" in goal_str:
            return FrameworkSelection(
                framework=FrameworkType.COMPETITIVE_INTELLIGENCE,
                rationale="Selected Competitive Intelligence to evaluate product differentiation and market rivals."
            )
        elif "talent" in intent_clean or "hiring" in goal_str or "recruitment" in goal_str:
            return FrameworkSelection(
                framework=FrameworkType.TALENT_INTELLIGENCE,
                rationale="Selected Talent Intelligence to optimize candidate pipelines and analyze hiring trends."
            )
        elif "m&a" in intent_clean or "mna" in intent_clean or "acquisition" in goal_str:
            return FrameworkSelection(
                framework=FrameworkType.MNA_ANALYSIS,
                rationale="Selected M&A Analysis for transactional assessment and corporate development."
            )
        elif "diligence" in intent_clean or "audit" in goal_str:
            return FrameworkSelection(
                framework=FrameworkType.DUE_DILIGENCE,
                rationale="Selected Due Diligence framework for audit and risk profiling."
            )
        elif "market_entry" in intent_clean or "expansion" in goal_str:
            return FrameworkSelection(
                framework=FrameworkType.MARKET_RESEARCH,
                rationale="Selected Market Research for entering new sectors and assessing demographics."
            )

        return FrameworkSelection(
            framework=FrameworkType.CONSULTING_REPORT,
            rationale="Selected general Consulting Report framework as the fallback standard format."
        )
