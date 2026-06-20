import json
import logging
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from services.research.json_llm import configured_json_generator
from services.planning.goal_extractor import GoalExtractor
from services.planning.framework_selector import FrameworkSelector

logger = logging.getLogger("uvicorn.error")

PLANNER_SYSTEM_PROMPT = """You are a Prompt Understanding Agent in a Business Intelligence platform.
Your task is to analyze the user request and translate it into a structured analysis plan.

Analyze the prompt and output a JSON object containing:
1. "target_company": The name of the target company to research/analyze (e.g. "Zoho" for "Sell TalentIQ to Zoho", "NVIDIA" for "Analyze NVIDIA valuation risk", "Apple" for "apple").
2. "intent": The primary objective of the prompt. Choose one of: "sales_strategy", "investment_analysis", "financial_analysis", "market_entry", "competitive_analysis", "general".
3. "research_goal": A description of the research goal (e.g. "Evaluate whether NVIDIA is an attractive investment today" or "Pitch TalentIQ AI Interview Platform to Zoho stakeholders").
4. "industry": The industry sector of the target company (e.g., "saas", "semiconductor", "banking", etc.).
5. "time_horizon": The time horizon of the research (e.g., "10_years", "current", "trailing_12_months").
6. "required_sources": A list of information source categories needed. Choose from: "sec", "yfinance", "news", "reddit", "company", "people", "hiring", "competitors", "web".
7. "required_analytics": A list of analytical components needed. Choose from: "revenue_growth", "earnings_growth", "valuation", "risk_analysis", "buyer_mapping", "pain_points", "hiring_trends", "competitive_position".
8. "report_framework": The report framework to use. Choose one of: "equity_research", "sales_account_plan", "sales_playbook", "consulting_report", "market_research", "competitive_brief", "general_brief".

Return ONLY the raw JSON object. Do not include markdown code block formatting (like ```json ... ```).
"""

class PromptPlan(BaseModel):
    target_company: str
    intent: str
    research_goal: str
    industry: str
    time_horizon: str
    required_sources: List[str] = Field(default_factory=list)
    required_analytics: List[str] = Field(default_factory=list)
    report_framework: str

class PromptUnderstandingAgent:
    """
    Analyzes user prompts to identify the core intent, target company, goal,
    industry, depth, required data sources, analytical steps, and framework.
    """
    def __init__(self, json_generator: Optional[Callable[[str, str], Awaitable[Dict[str, Any]]]] = None):
        self.json_generator = json_generator or configured_json_generator()
        self.goal_extractor = GoalExtractor(json_generator=self.json_generator)
        self.framework_selector = FrameworkSelector(json_generator=self.json_generator)

    async def plan(self, prompt: str) -> Dict[str, Any]:
        """
        Processes a prompt and returns the structured plan dictionary.
        Uses OpenAIJSONGenerator if configured, otherwise falls back to a heuristic/mock parser.
        """
        heuristic_plan = self._heuristic_plan(prompt)

        if self.json_generator:
            try:
                payload = await self.json_generator(
                    PLANNER_SYSTEM_PROMPT,
                    json.dumps({"prompt": prompt})
                )
                validated = PromptPlan.model_validate(payload)
                llm_plan = validated.model_dump(exclude_none=True)
                if self._has_financial_intent(prompt):
                    llm_plan["target_company"] = heuristic_plan["target_company"]
                    llm_plan["intent"] = heuristic_plan["intent"]
                    llm_plan["research_goal"] = heuristic_plan["research_goal"]
                    llm_plan["required_sources"] = heuristic_plan["required_sources"]
                    llm_plan["required_analytics"] = heuristic_plan["required_analytics"]
                    llm_plan["report_framework"] = heuristic_plan["report_framework"]
                return llm_plan
            except Exception as e:
                logger.warning(f"LLM prompt planning failed: {e}. Falling back to heuristic parser.")
        
        return heuristic_plan

    @staticmethod
    def _has_financial_intent(prompt: str) -> bool:
        return bool(re.search(
            r"\b(stock|stocks|share|shares|equity|invest|investment|valuation|financial|earnings|revenue)\b",
            prompt,
            flags=re.IGNORECASE,
        ))

    @staticmethod
    def _extract_financial_entity(prompt: str) -> str:
        """Extract a company phrase while removing financial request language."""
        text = re.sub(r"[?!.,]+$", "", prompt.strip())
        text = re.sub(
            r"^(?:please\s+)?(?:analyze|analyse|research|evaluate|review|investigate|show|get|check)\s+",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"^(?:should\s+i\s+)?(?:buy|sell|invest\s+in)\s+", "", text, flags=re.IGNORECASE)
        text = re.split(
            r"\s+(?:stock|stocks|shares?|equity|valuation|financials?|earnings|revenue)\b"
            r"|\s+as\s+(?:an?\s+)?(?:[\w-]+\s+){0,4}investment\b"
            r"|\s+for\s+(?:an?\s+)?investment\b",
            text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        text = re.sub(r"['’]s$", "", text.strip())
        text = re.sub(r"\s+(?:today|now|currently)$", "", text, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", text).strip()

    def _heuristic_plan(self, prompt: str) -> Dict[str, Any]:
        """
        Heuristic-based fallback planner when LLM is unavailable or fails.
        """
        lowered = prompt.lower().strip()

        if self._has_financial_intent(prompt):
            target = self._extract_financial_entity(prompt) or prompt.strip()
            investment_terms = bool(re.search(
                r"\b(stock|stocks|share|shares|equity|invest|investment|buy|sell)\b",
                lowered,
            ))
            intent = "investment_analysis" if investment_terms else "financial_analysis"
            analytics = ["revenue_growth", "earnings_growth", "valuation"]
            if "risk" in lowered:
                analytics.append("risk_analysis")
            years_match = re.search(r"(?:last|past|over\s+the\s+last)\s+(\d+)\s+years?", lowered)
            time_horizon = f"{years_match.group(1)}_years" if years_match else "current"
            sources = ["company", "sec", "yfinance"]
            if "only" not in lowered:
                sources.append("news")
            return {
                "target_company": target,
                "intent": intent,
                "research_goal": f"Evaluate {target}'s financial and investment profile",
                "industry": "general",
                "time_horizon": time_horizon,
                "required_sources": sources,
                "required_analytics": analytics,
                "report_framework": "equity_research"
            }
        
        # 1. Zoho sales strategy
        if "zoho" in lowered:
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
            
        # 2. NVIDIA investment / valuation
        if "nvidia" in lowered:
            # check query/prompt type
            if "financial" in lowered or "10 years" in lowered or "10_years" in lowered:
                return {
                    "target_company": "NVIDIA",
                    "intent": "financial_analysis",
                    "research_goal": "Analyze NVIDIA's financial performance over the last 10 years",
                    "industry": "semiconductor",
                    "time_horizon": "10_years",
                    "required_sources": ["sec", "yfinance", "news"],
                    "required_analytics": ["revenue_growth", "earnings_growth", "valuation"],
                    "report_framework": "equity_research"
                }
            elif "sell" in lowered or "sales" in lowered or "talentiq" in lowered:
                return {
                    "target_company": "NVIDIA",
                    "intent": "sales_strategy",
                    "research_goal": "Sell TalentIQ AI Interview Platform to NVIDIA",
                    "industry": "semiconductor",
                    "time_horizon": "current",
                    "required_sources": ["company", "people", "hiring", "news"],
                    "required_analytics": ["buyer_mapping", "pain_points", "hiring_trends"],
                    "report_framework": "sales_playbook"
                }
            else:
                # default NVIDIA investment
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
                
        # General clean up for target_company
        cleaned = prompt.strip()
        # strip common starting phrases
        for prefix in ("analyze ", "research ", "sell ", "pitch to ", "investigate "):
            if cleaned.lower().startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        # strip common ending phrases
        for suffix in (" valuation risk", " valuation", " profile", " risk", " performance"):
            if cleaned.lower().endswith(suffix):
                cleaned = cleaned[:-len(suffix)].strip()
                
        # default general fallback
        return {
            "target_company": cleaned or "Unknown",
            "intent": "general",
            "research_goal": f"Compile general business intelligence context for {cleaned}",
            "industry": "technology",
            "time_horizon": "current",
            "required_sources": ["company", "news"],
            "required_analytics": ["competitive_position"],
            "report_framework": "general_brief"
        }
