import json
import logging
from typing import Dict, Any
from services.models.planning_models import PlanningResult
from services.models.research_models import AgentResult
from services.agents.tool_router_agent import ToolRouterAgent
from services.agents.specialized.base import BaseResearchAgent
from services.research.json_llm import ModelRouter

# Import memory and engines
from services.research.compressor import ResearchMemory, ContextCompressor
from services.analytics.financial_engine import FinancialEngine
from services.analytics.valuation_engine import ValuationEngine
from services.analytics.risk_engine import RiskEngine
from services.analytics.growth_engine import GrowthEngine

logger = logging.getLogger("uvicorn.error")

class GenericLLMAgent(BaseResearchAgent):
    def __init__(self, agent_name: str, tools_needed: list[str]):
        self.agent_name = agent_name
        self.tools_needed = tools_needed
        self.model = ModelRouter().get_model_for_role(agent_name)
        # We no longer instantiate ResearchMemory here; it's injected/handled via memory_obj
        self.memory = None
        
    async def execute(self, planning: PlanningResult, tool_router: ToolRouterAgent, company_entity=None, previous_findings: list[str]=None, memory_obj=None) -> AgentResult:
        # We now rely entirely on the memory_obj built by AgentMemoryBuilder in host_agent.py
        from services.research.compressor import AGENT_PROMPTS
        
        system_prompt = AGENT_PROMPTS.get(self.agent_name)
        if not system_prompt:
            # Fallback if agent not in AGENT_PROMPTS
            target = company_entity.company_name if company_entity and hasattr(company_entity, "company_name") else planning.companies[0] if planning.companies else "Unknown"
            system_prompt = self._get_prompt(target)
            
        if memory_obj and hasattr(memory_obj, "to_user_prompt"):
            user_prompt = memory_obj.to_user_prompt()
            
            # If there's previous iteration findings, append them
            if previous_findings:
                user_prompt += f"\n\nPrevious Findings to build upon:\n{previous_findings}"
                
        else:
            # Fallback for agents that don't have a specific memory_obj (e.g. strategy_agent, ai_agent if not mapped)
            user_payload = {"agent": self.agent_name, "status": "No specific memory mapping"}
            if previous_findings:
                user_payload["previous_iteration_findings"] = previous_findings
            user_prompt = json.dumps(user_payload)
            
        logger.info(f"{self.agent_name} payload size: {len(system_prompt) + len(user_prompt)} chars")
        
        if self.model:
            try:
                payload = await self.model.generate_json(system_prompt, user_prompt)
                
                # Ensure evidence is empty as we don't need it anymore
                payload["evidence"] = []
                
                return AgentResult.model_validate(payload)
            except Exception as e:
                logger.warning(f"{self.agent_name} LLM failed: {e}. Returning fallback.")
                
        # Fallback
        return AgentResult(
            findings=[f"Basic finding from {self.agent_name}"],
            evidence=[],
            confidence=0.5
        )

    def _get_prompt(self, target: str) -> str:
        prompts = {
            "news_agent": f"""You are a News Intelligence Analyst.
Analyze only:
- recent news
- press releases
- earnings call headlines
- regulatory announcements

Ignore:
- valuation
- financial modeling
- competitors

Return ONLY valid JSON:
{{
  "findings": [],
  "sentiment": "positive|neutral|negative",
  "confidence": 0.0
}}""",
            "competitor_agent": f"""You are a Competitive Intelligence Analyst.
Tasks:
1. Identify top competitors
2. Compare products
3. Compare pricing
4. Compare market share
5. Identify threats

Return ONLY valid JSON:
{{
  "competitors": [],
  "advantages": [],
  "threats": [],
  "findings": [],
  "confidence": 0.0
}}""",
            "industry_agent": f"""You are an Industry Research Analyst.
Focus:
- TAM
- industry growth
- regulations
- market trends

Ignore company-specific financials.

Return ONLY valid JSON:
{{
  "industry_trends": [],
  "growth_drivers": [],
  "industry_risks": [],
  "findings": [],
  "confidence": 0.0
}}""",
            "financial_agent": f"""You are a Financial Analyst.
Focus only on:
- revenue
- margins
- EBITDA
- debt
- cash flow

Ignore:
- competitors
- news
- AI strategy

Return ONLY valid JSON:
{{
  "financial_findings": [],
  "metrics": {{}},
  "risks": [],
  "findings": [],
  "confidence": 0.0
}}"""
        }
        if self.agent_name in prompts:
            return prompts[self.agent_name]
            
        return f"""You are the {self.agent_name}. 
Your task is to analyze the context provided for {target} and produce a structured JSON report.
Ensure findings strictly relate to your specialization.

Output schema:
{{
  "findings": ["finding 1", "finding 2"],
  "confidence": 0.95
}}

Return ONLY the raw JSON object. Do not include markdown formatting.
"""

class DeterministicAgent(BaseResearchAgent):
    """
    An agent that fetches data via tools, processes via Python analytics engines,
    and returns it deterministically without invoking an LLM.
    """
    def __init__(self, agent_name: str, tools_needed: list[str]):
        self.agent_name = agent_name
        self.tools_needed = tools_needed
        self.memory = None
        
    async def execute(self, planning: PlanningResult, tool_router: ToolRouterAgent, company_entity=None, previous_findings: list[str]=None, memory_obj=None) -> AgentResult:
        # Determine target
        target = company_entity.company_name if company_entity and hasattr(company_entity, "company_name") else planning.companies[0] if planning.companies else "Unknown"
        
        # We don't fetch data here anymore, it's done centrally in host_agent
        # For DeterministicAgents, we just return a placeholder or use the raw data if we can get it from memory_obj
        raw_data = {}
        if memory_obj:
            raw_data = memory_obj if isinstance(memory_obj, dict) else getattr(memory_obj, "__dict__", {})
        
        # Process via Analytics Engines if applicable
        engine_output = None
        if self.agent_name == "financial_agent":
            engine_output = FinancialEngine.calculate(raw_data)
        elif self.agent_name == "valuation_agent":
            engine_output = ValuationEngine.calculate(raw_data)
        elif self.agent_name == "risk_agent":
            engine_output = RiskEngine.calculate(raw_data)
        elif self.agent_name == "growth_agent":
            engine_output = GrowthEngine.calculate(raw_data)
            
        findings_data = engine_output if engine_output else raw_data
        
        # Format directly to AgentResult bypassing LLM
        findings = [f"Raw data collected and analyzed for {target}:", str(findings_data)[:500] + "..."]
        
        return AgentResult(
            findings=findings,
            evidence=[],
            confidence=1.0
        )

class AgentFactory:
    _AGENTS = {
        "financial_agent": ["financial_data", "market_data"],
        "competitor_agent": ["company_profile", "market_data"],
        "industry_agent": ["news_feed"],
        "news_agent": ["news_feed"],
        "technology_agent": ["technology_stack", "company_profile"],
        "risk_agent": ["financial_data", "news_feed"],
        "valuation_agent": ["financial_data", "market_data"],
        "growth_agent": ["financial_data", "market_data"],
        "ai_agent": ["technology_stack", "news_feed"],
        "strategy_agent": ["company_profile", "financial_data"],
        "mna_agent": ["financial_data", "market_data"]
    }

    @classmethod
    def get_agent(cls, name: str) -> BaseResearchAgent:
        tools = cls._AGENTS.get(name, ["company_profile", "news_feed"])
        
        # Route to DeterministicAgent if it's an MCP data gathering agent
        deterministic_agents = [
            "risk_agent", "valuation_agent", 
            "growth_agent", "mna_agent"
        ]
        
        if name in deterministic_agents:
            return DeterministicAgent(name, tools)
            
        return GenericLLMAgent(name, tools)
