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
            key = ev.source
            attr = ev.attribute
            val = ev.value
            
            # Map by attribute or key based on the emitted provider sources
            if key in ["sec_edgar", "sec_edgar_10k", "yfinance"]:
                if "financials" not in raw_context_dict:
                    raw_context_dict["financials"] = {}
                raw_context_dict["financials"][attr] = val
            elif key == "news_intelligence_pipeline":
                if "news" not in raw_context_dict:
                    raw_context_dict["news"] = []
                if isinstance(val, list):
                    for item in val:
                        raw_context_dict["news"].append({
                            "title": item.get("headline", item.get("title", "")),
                            "url": item.get("url", ev.source_url or ""),
                            "date": item.get("published_at", item.get("date")),
                            "snippet": item.get("summary", item.get("snippet", "")),
                            "type": "general"
                        })
                elif isinstance(val, dict):
                    raw_context_dict["news"].append({
                        "title": val.get("headline", val.get("title", "")),
                        "url": ev.source_url or val.get("url", ""),
                        "date": val.get("published_at", val.get("date")),
                        "snippet": val.get("summary", val.get("snippet", "")),
                        "type": "general"
                    })
                else:
                    raw_context_dict["news"].append(val)
            elif key in ["company_profile", "crunchbase", "similarweb", "web_technology_profile"]:
                if "profile" not in raw_context_dict:
                    raw_context_dict["profile"] = {}
                raw_context_dict["profile"][attr] = val
            elif key in ["people_pipeline", "indeed", "github", "glassdoor"]:
                if "people" not in raw_context_dict:
                    raw_context_dict["people"] = {}
                raw_context_dict["people"][attr] = val
            elif key in ["reddit", "stocktwits", "hackernews", "social_intel"]:
                if "social" not in raw_context_dict:
                    raw_context_dict["social"] = {}
                raw_context_dict["social"][attr] = val
            else:
                raw_context_dict[attr] = val

        analytics_data = FinancialCalculator.generate_analytics(raw_context_dict.get("financials", {}))

        evidence_graph = EvidenceGraph(nodes=[
            EvidenceNode(id=ev.id, fact=str(ev.value)[:100], agent=ev.source)
            for ev in all_evidence
        ])

        # Re-build fully populated ResearchContext to pass to Synthesizer and UIAgent
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

        tech_stack_raw = raw_context_dict.get("profile", {}).get("technology_stack", [])
        if isinstance(tech_stack_raw, dict):
            tech_stack_raw = tech_stack_raw.get("technologies", [])
            
        financial_data_res = None
        if raw_context_dict.get("financials"):
            # Ensure safe kwargs mapping
            financial_data_res = FinancialData(**raw_context_dict.get("financials", {}))

        context_obj = ResearchContext(
            entity=entity_res,
            profile=profile_res,
            financials=financial_data_res,
            analytics=analytics_data,
            news=raw_context_dict.get("news", []),
            technology_stack=tech_stack_raw,
            leadership=raw_context_dict.get("profile", {}).get("leadership", []),
            competitors=raw_context_dict.get("profile", {}).get("competitors", []),
            competitive_positioning=raw_context_dict.get("competitive_positioning"),
            swot=raw_context_dict.get("swot"),
            risk_factors=raw_context_dict.get("financials", {}).get("risk_factors_text", []) if isinstance(raw_context_dict.get("financials", {}).get("risk_factors_text", []), list) else [],
            management_commentary=raw_context_dict.get("financials", {}).get("mda_text", []) if isinstance(raw_context_dict.get("financials", {}).get("mda_text", []), list) else [],
            industry_context=None,
            evidence_graph=evidence_graph
        )
        context_dict = context_obj.model_dump()

        # 4. Meta Synthesis
        logger.info("START synthesis")
        synthesis = await self.synthesizer.execute(plan, context_dict, target)
        
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
                
        # Append Synthesis into Context object before UIAgent
        context_obj.draft_report = DraftReport(**synthesis_dict)
        if critique_dict:
            context_obj.critique = CriticResult(**critique_dict)
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
