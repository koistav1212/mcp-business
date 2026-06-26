import asyncio
from services.agents.planner_agent import PlannerAgent
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
from services.knowledge.evidence_store import EvidenceStore
from services.knowledge.knowledge_router import KnowledgeRouter
from services.knowledge.views.view_factory import ViewFactory

logger = logging.getLogger("uvicorn.error")

class HostAgent:
    def __init__(self):
        self.entity_extractor = EntityExtractorAgent()
        self.planner = PlannerAgent()
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
        
        # 2. (Deprecated) Research Direction bypassed by ExecutionPlan
        # 3. Knowledge Layer Setup
        self.memory = ResearchMemory()
        evidence_store = EvidenceStore()
        knowledge_router = KnowledgeRouter(self.tool_router, evidence_store)
        
        # Determine target to pass down
        if company_entity and hasattr(company_entity, "company") and company_entity.company:
            target = company_entity.company
        elif hasattr(planning, "company") and planning.company:
            target = planning.company
        elif hasattr(planning, "entities") and planning.entities:
            target = planning.entities[0]
        else:
            target = "Unknown"
            
        target_ticker = company_entity.ticker if company_entity and hasattr(company_entity, "ticker") and company_entity.ticker else target
        target_cik = company_entity.cik if company_entity and hasattr(company_entity, "cik") else target_ticker

        # Backwards compatibility context for UIAgent later
        # We fetch all required sources upfront via knowledge_router to prepopulate evidence_store
        logger.info("START mcp_tools via KnowledgeRouter")
        raw_context_dict = {}
        for source in planning.required_sources:
            ev = await knowledge_router.get_evidence(source, target)
            # Store something in raw_context_dict so UIAgent doesn't break
            if ev:
                raw_context_dict[source] = ev[0].value
                
        # Also fetch sources for individual tasks to prepopulate store
        for task in planning.research_tasks:
            for source in task.required_sources:
                await knowledge_router.get_evidence(source, target)

        # 4. Wave-based Agent Execution
        sem = asyncio.Semaphore(5)

        async def guarded_call(coro):
            async with sem:
                return await coro
        
        current_agent_results = {}
        
        for wave in planning.execution_waves:
            logger.info(f"START Wave {wave.wave_id} with {len(wave.tasks)} tasks.")
            agent_tasks = []
            agent_names_in_wave = []
            
            for task in wave.tasks:
                agent_name = task.owner_agent
                
                if agent_name == "entity_extractor":
                    current_agent_results[agent_name] = company_entity
                    continue
                    
                agent = AgentFactory.get_agent(agent_name)
                if not agent:
                    logger.warning(f"Agent {agent_name} not found in factory.")
                    continue
                    
                # Extract previous findings from dependencies
                previous_findings = []
                for dep in task.dependencies:
                    dep_task = next((t for t in planning.research_tasks if t.task_id == dep), None)
                    if dep_task and dep_task.owner_agent in current_agent_results:
                        res = current_agent_results[dep_task.owner_agent]
                        if hasattr(res, "findings"):
                            previous_findings.extend(res.findings)
                            
                # Build context via KnowledgeView
                knowledge_view = ViewFactory.get(agent_name)
                # Pass 'target' as the entity name string
                context = knowledge_view.build(target, evidence_store)
                
                coro = agent.execute(planning, self.tool_router, company_entity=company_entity, previous_findings=previous_findings if previous_findings else None, knowledge_view=context)
                agent_tasks.append(guarded_call(coro))
                agent_names_in_wave.append(agent_name)
                
            if agent_tasks:
                agent_results_list = await asyncio.gather(*agent_tasks)
                
                for agent_name, result in zip(agent_names_in_wave, agent_results_list):
                    current_agent_results[agent_name] = result
                    if hasattr(result, "model_dump"):
                        self.memory.store_agent_output(agent_name, result.model_dump())
                    else:
                        self.memory.store_agent_output(agent_name, {"findings": result.findings} if hasattr(result, "findings") else {})

            
        # 3.5 Synchronization Barrier
        logger.info("Verifying Synchronization Barrier...")
        missing_agents = []
        for task in planning.research_tasks:
            agent = task.owner_agent
            if agent not in current_agent_results and agent != "entity_extractor":
                missing_agents.append(agent)
                
        if missing_agents:
            logger.warning(f"Synchronization Barrier Warning: The following planned agents did not complete successfully: {missing_agents}")
            # Depending on strictness, we could raise an error or halt.
            # We'll log it as a critical warning and proceed with partial data for now.
            
        # 4. Meta Synthesis
        logger.info("START synthesis")
        synthesis = await self.synthesizer.execute(current_agent_results, planning, planning)
        
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
