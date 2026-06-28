import asyncio
import logging
from typing import Dict, Any

from services.agents.planner_agent import PlannerAgent
from services.agents.tool_router_agent import ToolRouterAgent
from services.agents.synthesizer_agent import SynthesizerAgent
from services.agents.critic_agent import CriticAgent
from services.agents.ui_agent import UIAgent
from services.agents.entity_extractor_agent import EntityExtractorAgent

from services.planning.task_scheduler import TaskScheduler
from services.research.compressor import ResearchMemory
from services.research.models import (
    ResearchContext, EvidenceGraph, EvidenceNode, DraftReport, 
    CompanyProfile, FinancialData, EntityResolution, CriticResult
)
from services.analytics.financial_calculator import FinancialCalculator
from services.knowledge.evidence_store import EvidenceStore
from services.knowledge.knowledge_router import KnowledgeRouter
from services.artifacts.artifact_writer import ArtifactWriter

logger = logging.getLogger("uvicorn.error")

class HostAgent:
    def __init__(self):
        self.entity_extractor = EntityExtractorAgent()
        self.planner = PlannerAgent()
        self.tool_router = ToolRouterAgent()
        self.synthesizer = SynthesizerAgent()
        self.critic = CriticAgent()
        self.ui_agent = UIAgent()

    async def run(self, query: str) -> Dict[str, Any]:
        ArtifactWriter.write_json("agent_inputs/session_query.json", {"query": query})
        
        # 0. Entity Extraction
        logger.info("START entity_extractor")
        company_entity = await self.entity_extractor.execute(query)
        if company_entity:
            ArtifactWriter.write_json("agent_outputs/entity_extractor.json", company_entity.model_dump() if hasattr(company_entity, "model_dump") else company_entity)
        
        # Build base entity data dictionary for the orchestrator
        entity_data = {}
        if company_entity:
            entity_data["canonical_name"] = getattr(company_entity, "company", query)
            entity_data["ticker"] = getattr(company_entity, "ticker", None)
            entity_data["cik"] = getattr(company_entity, "cik", None)
        else:
            entity_data["canonical_name"] = query

        # 1. Planning
        logger.info("START planner")
        plan = await self.planner.execute(query)
        ArtifactWriter.write_json("agent_outputs/execution_plan.json", plan.model_dump() if hasattr(plan, "model_dump") else plan)
        
        # Determine target to pass down
        target = entity_data.get("canonical_name", query)

        # 2. Knowledge Layer Setup
        self.memory = ResearchMemory()
        evidence_store = EvidenceStore()
        knowledge_router = KnowledgeRouter(self.tool_router, evidence_store)
        scheduler = TaskScheduler(knowledge_router)
        
        # 3. Wave-based Agent Execution (via TaskScheduler)
        logger.info("START mcp_tools via TaskScheduler")
        # Prepopulate direct domains if the planner requires them
        for provider_name in plan.required_providers:
            await knowledge_router.get_evidence(provider_name, target)
            
        # Execute the formal execution plan
        await scheduler.execute(plan, entity_data)
        
        # Collect raw evidence from EvidenceStore to populate UI Context
        raw_context_dict = {}
        all_evidence = evidence_store.get_all()
        for ev in all_evidence:
            # Depending on how the provider writes its attribute/source,
            # we attempt to map it to the raw_context_dict
            key = ev.source
            if "sec" in key or "finance" in key:
                # Merge into financials
                if "financials" not in raw_context_dict:
                    raw_context_dict["financials"] = {}
                # This is a simplification; in reality, we'd merge the dicts
                if isinstance(ev.value, dict):
                    raw_context_dict["financials"].update(ev.value)
            elif "news" in key:
                if "news" not in raw_context_dict:
                    raw_context_dict["news"] = []
                if isinstance(ev.value, list):
                    raw_context_dict["news"].extend(ev.value)
            elif "company" in key or "web" in key:
                if "profile" not in raw_context_dict:
                    raw_context_dict["profile"] = {}
                if isinstance(ev.value, dict):
                    raw_context_dict["profile"].update(ev.value)
            elif "people" in key:
                if "leadership" not in raw_context_dict:
                    raw_context_dict["leadership"] = []
                if isinstance(ev.value, list):
                    raw_context_dict["leadership"].extend(ev.value)
            else:
                raw_context_dict[key] = ev.value

        # 4. Meta Synthesis
        logger.info("START synthesis")
        synthesis = await self.synthesizer.execute(plan, evidence_store, target)
        
        synthesis_dump = synthesis.model_dump() if hasattr(synthesis, "model_dump") else (synthesis if isinstance(synthesis, dict) else getattr(synthesis, "__dict__", {}))
        ArtifactWriter.write_json("synthesis/synthesis_result.json", synthesis_dump)
        
        # 5. Review/Critique
        logger.info("START critic")
        critique = await self.critic.review(synthesis) if hasattr(self.critic, "review") else None
        
        try:
            critique_dict = critique.model_dump() if critique else None
        except AttributeError:
            critique_dict = getattr(critique, '__dict__', str(critique)) if not isinstance(critique, dict) else critique

        if critique_dict:
            ArtifactWriter.write_json("critic/critic_result.json", critique_dict)

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

        analytics_data = FinancialCalculator.generate_analytics(raw_context_dict.get("financials", {}))

        evidence_graph = EvidenceGraph(nodes=[
            EvidenceNode(id=ev.id, fact=str(ev.value)[:100], agent=ev.source)
            for ev in all_evidence
        ])

        # Re-build fully populated ResearchContext for UIAgent
        entity_res = None
        if company_entity:
            entity_res = EntityResolution(
                company_name=getattr(company_entity, "company", target),
                ticker=getattr(company_entity, "ticker", None),
                cik=getattr(company_entity, "cik", None),
                exchange=getattr(company_entity, "exchange", None),
                website=getattr(company_entity, "website", None),
                confidence=getattr(company_entity, "confidence", 1.0)
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
        ArtifactWriter.write_json("ui/ui_response.json", ui)
        
        final_result = {
            "context": synthesis_dict,
            "critique": critique_dict,
            **ui
        }
        
        ArtifactWriter.write_json("final/final_context.json", context_dict)
        ArtifactWriter.write_json("final/final_result.json", final_result)

        return final_result
