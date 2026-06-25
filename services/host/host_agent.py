import asyncio
from services.agents.planner_agent import PlannerAgent
from services.agents.research_director_agent import ResearchDirectorAgent
from services.agents.tool_router_agent import ToolRouterAgent
from services.agents.synthesizer_agent import SynthesizerAgent
from services.agents.critic_agent import CriticAgent
from services.agents.ui_agent import UIAgent
from services.agents.specialized.factory import AgentFactory
import logging
from services.agents.entity_extractor_agent import EntityExtractorAgent
from services.research.compressor import ResearchMemory, AgentMemoryBuilder
from services.research.models import ResearchContext, EvidenceGraph, EvidenceNode, DraftReport, CompanyProfile, FinancialData, EntityResolution, CriticResult
from services.analytics.financial_calculator import FinancialCalculator

logger = logging.getLogger("uvicorn.error")

class HostAgent:
    def __init__(self):
        self.entity_extractor = EntityExtractorAgent()
        self.planner = PlannerAgent()
        self.research_director = ResearchDirectorAgent()
        self.tool_router = ToolRouterAgent()
        self.synthesizer = SynthesizerAgent()
        self.critic = CriticAgent()
        self.ui_agent = UIAgent()

    async def run(self, query: str):
        # 0. Entity Extraction
        logger.info("START entity_extractor")
        company_entity = await self.entity_extractor.execute(query)

        # 1. Planning
        logger.info("START planner")
        planning = await self.planner.execute(query)
        
        # 2. Research Direction
        logger.info("START director")
        mission = await self.research_director.execute(planning)
        
        # 3. Centralized Tool Execution & Compression
        self.memory = ResearchMemory()
        
        target = company_entity.company_name if company_entity and hasattr(company_entity, "company_name") else planning.companies[0] if planning.companies else "Unknown"
        target_ticker = company_entity.ticker if company_entity and hasattr(company_entity, "ticker") else target
        target_cik = company_entity.cik if company_entity and hasattr(company_entity, "cik") else target_ticker

        all_needed_tools = set()
        for agent in mission.agents:
            all_needed_tools.update(AgentFactory._AGENTS.get(agent, []))
            
        tool_requests = {}
        for tool in all_needed_tools:
            if tool == "financial_data": tool_requests[tool] = target_cik
            elif tool == "market_data": tool_requests[tool] = target_ticker
            else: tool_requests[tool] = target
            
        logger.info("START mcp_tools")
        raw_data = await self.tool_router.execute_batch(tool_requests)
        
        # Store raw responses in local memory
        for tool_name, data in raw_data.items():
            self.memory.store_raw("mcp", tool_name, data)

        # Build Context Dict for Memory Builder
        raw_context_dict = {
            "profile": raw_data.get("company_profile"),
            "entity": company_entity.model_dump() if company_entity and hasattr(company_entity, "model_dump") else {},
            "financials": raw_data.get("financial_data"),
            "news": raw_data.get("news_feed"),
            "technology_stack": raw_data.get("technology_stack"),
            # We don't have competitor_analysis tool anymore, maybe it's inside profile
            "competitors": raw_data.get("company_profile", {}).get("competitors", []) if isinstance(raw_data.get("company_profile"), dict) else [],
            "social_sentiment": raw_data.get("news_feed", {}).get("sentiment", {}) if isinstance(raw_data.get("news_feed"), dict) else {},
            "hiring_signals": raw_data.get("company_profile", {}).get("hiring", []) if isinstance(raw_data.get("company_profile"), dict) else [],
        }

        # Build Agent Memories
        intent_dict = planning.model_dump() if hasattr(planning, "model_dump") else (planning if isinstance(planning, dict) else getattr(planning, "__dict__", {}))
        agent_memories = AgentMemoryBuilder.build_all(raw_context_dict, intent_dict)

        # 4. Specialized Agent Execution
        iterations = getattr(mission, "iterations", 1)
        
        STAGES = [
            ["news_agent", "industry_agent"],
            ["competitor_agent", "financial_agent"],
            ["strategy_agent", "ai_agent", "tech_agent", "risk_agent"]
        ]
        
        sem = asyncio.Semaphore(2)

        async def guarded_call(coro):
            async with sem:
                return await coro
        
        current_agent_results = {}
        for loop_idx in range(iterations):
            mission_agents = set(mission.agents)
            staged_execution_plan = []
            
            for stage in STAGES:
                stage_agents = [a for a in stage if a in mission_agents]
                if stage_agents:
                    staged_execution_plan.append(stage_agents)
                mission_agents -= set(stage_agents)
                
            if mission_agents:
                staged_execution_plan.append(list(mission_agents))
                
            for stage_agents in staged_execution_plan:
                agent_tasks = []
                for agent_name in stage_agents:
                    agent = AgentFactory.get_agent(agent_name)
                    # Get the built memory object for this agent
                    memory_obj = agent_memories.get(agent_name)
                    
                    previous_findings = current_agent_results.get(agent_name, None)
                    prev_findings_list = previous_findings.findings if hasattr(previous_findings, "findings") else None
                    
                    coro = agent.execute(planning, self.tool_router, company_entity=company_entity, previous_findings=prev_findings_list, memory_obj=memory_obj)
                    agent_tasks.append(guarded_call(coro))
                    
                # Execute this stage concurrently
                agent_results_list = await asyncio.gather(*agent_tasks)
                
                # Update the accumulated results
                for agent_name, result in zip(stage_agents, agent_results_list):
                    current_agent_results[agent_name] = result
                    if hasattr(result, "model_dump"):
                        self.memory.store_agent_output(agent_name, result.model_dump())
                    else:
                        self.memory.store_agent_output(agent_name, {"findings": result.findings} if hasattr(result, "findings") else {})

            
        # 4. Meta Synthesis
        logger.info("START synthesis")
        synthesis = await self.synthesizer.execute(current_agent_results, planning, mission)
        
        # 5. Review/Critique
        logger.info("START critic")
        critique = await self.critic.review(synthesis) if hasattr(self.critic, "review") else None
        
        # Assuming critique could be a model
        try:
            critique_dict = critique.model_dump() if critique else None
        except AttributeError:
            critique_dict = getattr(critique, '__dict__', str(critique)) if not isinstance(critique, dict) else critique

        # Prepare context dict for UI Agent
        # THIS was the main bug: We must pass ALL fields to UI Agent!
        if isinstance(synthesis, str):
            try:
                import json
                synthesis_dict = json.loads(synthesis)
            except Exception:
                synthesis_dict = {"executive_summary": synthesis, "key_findings": [], "risks": [], "opportunities": [], "recommendations": []}
        else:
            synthesis_dict = synthesis.model_dump() if hasattr(synthesis, "model_dump") else (synthesis if isinstance(synthesis, dict) else getattr(synthesis, "__dict__", {}))

        # Format strings to CitedInsight if needed
        for key in ["key_findings", "risks", "opportunities", "recommendations"]:
            if key in synthesis_dict:
                formatted_list = []
                for item in synthesis_dict[key]:
                    if isinstance(item, str):
                        formatted_list.append({"insight": item, "evidence_ids": []})
                    else:
                        formatted_list.append(item)
                synthesis_dict[key] = formatted_list

        # Calculate analytics
        analytics_data = FinancialCalculator.generate_analytics(raw_context_dict.get("financials", {}))

        # Build dummy evidence graph
        evidence_graph = EvidenceGraph(nodes=[
            EvidenceNode(id=f"EV-{i}", fact=str(r), agent=name)
            for i, (name, r) in enumerate(current_agent_results.items())
        ])

        # Re-build fully populated ResearchContext for UIAgent
        entity_data = raw_context_dict.get("entity", {})
        entity_res = None
        if entity_data:
            entity_res = EntityResolution(
                company_name=entity_data.get("company", entity_data.get("company_name", "Unknown")),
                ticker=entity_data.get("ticker"),
                cik=entity_data.get("cik"),
                exchange=entity_data.get("exchange"),
                website=entity_data.get("website"),
                confidence=entity_data.get("confidence", 1.0)
            )

        profile_data = raw_context_dict.get("profile", {})
        profile_res = None
        if profile_data:
            profile_data_copy = profile_data.copy()
            hq = profile_data_copy.get("headquarters")
            emp = profile_data_copy.get("employee_count")
            if hq is not None and not isinstance(hq, dict):
                profile_data_copy["headquarters"] = {"value": hq}
            if emp is not None and not isinstance(emp, dict):
                profile_data_copy["employee_count"] = {"value": emp}
            profile_res = CompanyProfile(**profile_data_copy)

        tech_stack_raw = raw_context_dict.get("technology_stack", [])
        if isinstance(tech_stack_raw, dict):
            tech_stack_raw = tech_stack_raw.get("technologies", [])

        context_obj = ResearchContext(
            entity=entity_res,
            profile=profile_res,
            financials=FinancialData(**raw_context_dict.get("financials", {})) if raw_context_dict.get("financials") else None,
            analytics=analytics_data,
            news=raw_context_dict.get("news", []),
            technology_stack=tech_stack_raw,
            leadership=raw_context_dict.get("leadership", []),
            competitors=raw_context_dict.get("competitors", []),
            competitive_positioning=raw_context_dict.get("competitive_positioning"),
            swot=raw_context_dict.get("swot"),
            risk_factors=raw_context_dict.get("risk_factors", []),
            management_commentary=raw_context_dict.get("management_commentary", []),
            industry_context=raw_context_dict.get("industry_context"),
            draft_report=DraftReport(**synthesis_dict),
            critique=CriticResult(**critique_dict) if critique_dict else None,
            evidence_graph=evidence_graph
        )
        
        context_dict = context_obj.model_dump()


        # 6. UI Generation
        logger.info("START ui")
        ui = await self.ui_agent.execute(query, context_dict)

        return {
            "context": synthesis_dict,
            "critique": critique_dict,
            **ui
        }
