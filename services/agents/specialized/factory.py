import json
import logging
from typing import Dict, Any
from services.models.planning_models import PlanningResult
from services.models.research_models import AgentResult, Finding
from services.agents.tool_router_agent import ToolRouterAgent
from services.agents.specialized.base import BaseResearchAgent
from services.llm.provider_router import ProviderRouter

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
        # We no longer instantiate ResearchMemory here; it's injected/handled via memory_obj
        self.memory = None
        
    async def execute(self, planning: PlanningResult, tool_router: ToolRouterAgent, company_entity=None, previous_findings: list[str]=None, knowledge_view=None) -> AgentResult:
        
        # Extract target safely
        if company_entity and hasattr(company_entity, "company") and company_entity.company:
            target = company_entity.company
        elif hasattr(planning, "company") and planning.company:
            target = planning.company
        elif hasattr(planning, "entities") and planning.entities:
            target = planning.entities[0]
        else:
            target = "Unknown"
            
        system_prompt = self._get_prompt(target)
            
        # Serialize the knowledge_view list of ResearchEvidence
        if knowledge_view is not None:
            view_dicts = [ev.model_dump() if hasattr(ev, "model_dump") else (ev if isinstance(ev, dict) else getattr(ev, "__dict__", {})) for ev in knowledge_view]
            user_payload = {"agent": self.agent_name, "evidence": view_dicts}
        else:
            user_payload = {"agent": self.agent_name, "evidence": []}
            
        from services.artifacts.artifact_writer import ArtifactWriter
        ArtifactWriter.write_json(f"knowledge_views/{self.agent_name}.json", user_payload)

        # If there's previous iteration findings, append them
        if previous_findings:
            user_payload["previous_iteration_findings"] = previous_findings
            
        user_prompt = json.dumps(user_payload, default=str)
            
        logger.info(f"{self.agent_name} payload size: {len(system_prompt) + len(user_prompt)} chars")
        
        if True:
            try:
                # Relying on router to enforce token limits natively
                payload = await ProviderRouter.generate_json(
                    agent_name=self.agent_name,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt
                )
                
                if not isinstance(payload, dict):
                    raise ValueError(f"LLM returned {type(payload)} instead of dict. Content: {payload}")
                
                # Ensure evidence is empty as we don't need to pass it back
                payload["evidence"] = []
                
                return AgentResult.model_validate(payload)
            except Exception as e:
                logger.warning(f"{self.agent_name} LLM failed: {e}. Returning fallback.")
                
        # Fallback
        return AgentResult(
            findings=[
                Finding(
                    id=f"FB-{self.agent_name}",
                    description=f"Basic finding from {self.agent_name}",
                    evidence_refs=[],
                    confidence=0.5
                )
            ],
            evidence=[],
            confidence=0.5
        )

    def _get_prompt(self, target: str) -> str:
        universal_rules = (
            "You are ONLY allowed to use the evidence supplied.\n"
            "Never assume missing facts.\n"
            "Never ask for additional company information.\n"
            "Ignore any domain outside your specialization.\n"
            "Return structured findings only.\n"
            "If confidence < 0.7 return NeedMoreEvidence."
        )
        prompts = {
            "news_agent": f"""You are a Market Intelligence Analyst.
Analyze ONLY supplied news.

Tasks:
- Build Timeline
- Identify Catalysts
- Identify Market Moving Events
- Estimate Sentiment
- Extract Risks
- Extract Opportunities
- Detect Contradictions

Never discuss:
- Financial Statements
- SWOT
- Technology
- Products
- Valuation

Return ONLY valid JSON:
{{
  "timeline": [],
  "catalysts": [],
  "sentiment": "positive|neutral|negative",
  "evidence_ids": [],
  "confidence": 0.0,
  "findings": []
}}
{universal_rules}""",
            "competitor_agent": f"""You are a Competitive Intelligence Analyst.
Tasks: Identify top competitors, Compare products, Compare pricing, Compare market share, Identify threats.

Return ONLY valid JSON:
{{
  "competitors": [],
  "advantages": [],
  "threats": [],
  "findings": [],
  "confidence": 0.0
}}
{universal_rules}""",
            "industry_agent": f"""You are an Industry Research Analyst.
Focus: TAM, industry growth, regulations, market trends.

Return ONLY valid JSON:
{{
  "industry_trends": [],
  "growth_drivers": [],
  "industry_risks": [],
  "findings": [],
  "confidence": 0.0
}}
{universal_rules}""",
            "financial_agent": f"""You are a Financial Analyst.
Focus only on: revenue, margins, EBITDA, debt, cash flow.

Return ONLY valid JSON:
{{
  "financial_findings": [],
  "metrics": {{}},
  "risks": [],
  "findings": [],
  "confidence": 0.0
}}
{universal_rules}"""
        }
        if self.agent_name in prompts:
            return prompts[self.agent_name]
            
        return f"""You are the {self.agent_name}. 
Your task is to analyze the context provided for {target} and produce a structured JSON report.
{universal_rules}

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
        
    async def execute(self, planning: PlanningResult, tool_router: ToolRouterAgent, company_entity=None, previous_findings: list[str]=None, knowledge_view=None) -> AgentResult:
        # Extract target safely
        if company_entity and hasattr(company_entity, "company") and company_entity.company:
            target = company_entity.company
        elif hasattr(planning, "company") and planning.company:
            target = planning.company
        elif hasattr(planning, "entities") and planning.entities:
            target = planning.entities[0]
        else:
            target = "Unknown"
        
        # Format the context dict for engines to ingest
        raw_data = {}
        if knowledge_view:
            raw_data = {"evidence": [ev.model_dump() if hasattr(ev, "model_dump") else (ev if isinstance(ev, dict) else getattr(ev, "__dict__", {})) for ev in knowledge_view]}
        
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
        findings = [
            Finding(
                id=f"RAW-{self.agent_name}-1",
                description=f"Raw data collected and analyzed for {target}:",
                evidence_refs=[],
                confidence=1.0
            ),
            Finding(
                id=f"RAW-{self.agent_name}-2",
                description=str(findings_data)[:500] + "...",
                evidence_refs=[],
                confidence=1.0
            )
        ]
        
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
