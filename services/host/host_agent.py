import asyncio
import logging
from typing import Dict, Any, List

from services.agents.planner_agent import PlannerAgent
from services.agents.tool_router_agent import ToolRouterAgent
from services.agents.entity_extractor_agent import EntityExtractorAgent
from services.knowledge.evidence_store import EvidenceStore
from services.knowledge.knowledge_router import KnowledgeRouter
from services.planning.task_scheduler import TaskScheduler
from services.artifacts.artifact_writer import ArtifactWriter

from services.storage.event_store import EventStore
from services.storage.insight_store import InsightStore
from services.storage.narrative_store import NarrativeStore
from services.agents.event_extractor_agent import EventExtractorAgent
from services.intelligence.event_processor import EventProcessor
from services.agents.theme_detection_agent import ThemeDetectionAgent
from services.agents.section_generators.financial_section_generator import FinancialSectionGenerator
from services.agents.section_generators.competitor_section_generator import CompetitorSectionGenerator
from services.agents.section_generators.operations_section_generator import OperationsSectionGenerator
from services.agents.section_generators.technology_section_generator import TechnologySectionGenerator
from services.agents.section_generators.risk_section_generator import RiskSectionGenerator
from services.agents.section_generators.market_section_generator import MarketSectionGenerator
from services.agents.section_generators.social_section_generator import SocialSectionGenerator
from services.agents.cross_provider_reasoning_agent import CrossProviderReasoningAgent
from services.agents.synthesizer_agent import SynthesizerAgent
from services.agents.critic_agent import CriticAgent
from services.ui.page_composer import PageComposerAgent
from services.schemas.insight import ResearchContext

logger = logging.getLogger("uvicorn.error")

class HostAgent:
    def __init__(self):
        self.entity_extractor = EntityExtractorAgent()
        self.planner = PlannerAgent()
        self.tool_router = ToolRouterAgent()
        
        # New agents
        self.event_extractor = EventExtractorAgent()
        self.theme_detector = ThemeDetectionAgent()
        self.cross_provider_reasoner = CrossProviderReasoningAgent()
        self.synthesizer = SynthesizerAgent()
        self.critic_agent = CriticAgent()
        self.page_composer = PageComposerAgent()
        
        # Stores
        self.evidence_store = EvidenceStore()
        self.event_store = EventStore()
        self.insight_store = InsightStore()
        self.narrative_store = NarrativeStore()

    async def run(self, query: str) -> Dict[str, Any]:
        ArtifactWriter.write_json("agent_inputs/session_query.json", {"query": query})
        
        # 0. Entity Extraction
        logger.info("START entity_extractor")
        await asyncio.sleep(0.5)
        company_entity = await self.entity_extractor.execute(query)
        entity_name = getattr(company_entity, "company", None) or getattr(company_entity, "company_name", None) if company_entity else None
        entity_name = entity_name or query
        ArtifactWriter.write_json("pipeline/1_entity.json", {"entity": entity_name})
        
        # 1. Planning
        logger.info("START planner")
        await asyncio.sleep(0.5)
        plan = await self.planner.execute(query, company_entity)
        ArtifactWriter.write_json("pipeline/2_plan.json", {"plan": plan.model_dump() if hasattr(plan, "model_dump") else plan})
        
        # 2. Knowledge Layer (Providers -> Evidence)
        knowledge_router = KnowledgeRouter(self.tool_router, self.evidence_store)
        scheduler = TaskScheduler(knowledge_router)
        logger.info("START mcp_tools via TaskScheduler (Providers -> Evidence)")
        
        entity_data = self._build_scheduler_entity_data(company_entity, entity_name)
        await scheduler.execute(plan, entity_data)
        
        # We now have raw evidence in self.evidence_store.
        raw_evidence = self.evidence_store.get_all()
        ArtifactWriter.write_json("pipeline/3_evidence.json", {"evidence": [e.model_dump() if hasattr(e, "model_dump") else e for e in raw_evidence]})
        
        # 3. Evidence Graph Builder (No LLM)
        logger.info("START Evidence Graph Builder")
        from services.research.evidence_graph import EvidenceGraphBuilder
        graph_builder = EvidenceGraphBuilder()
        evidence_graph = graph_builder.build(raw_evidence, entity_name)
        ArtifactWriter.write_json("pipeline/evidence_graph.json", evidence_graph)

        # 4. Event Extractor (LLM, Scoped to Recent Documents only)
        logger.info("START Event Extractor")
        recent_documents = []
        for ev in raw_evidence:
            val = getattr(ev, "value", None)
            source = getattr(ev, "source", "").lower()
            if not val:
                continue
            if "news" in source or "reddit" in source or "social" in source:
                if isinstance(val, dict) and "articles" in val:
                    articles = val.get("articles", [])
                else:
                    articles = val if isinstance(val, list) else [val]
                    
                for art in articles:
                    if isinstance(art, dict):
                        recent_documents.append({
                            "headline": art.get("headline", art.get("title", "")),
                            "summary": art.get("summary", art.get("snippet", "")),
                            "timestamp": art.get("date", art.get("timestamp", getattr(ev, "retrieved_at", "").isoformat() if hasattr(ev, "retrieved_at") else "")),
                            "url": art.get("url", getattr(ev, "source_url", ""))
                        })
                    else:
                        recent_documents.append({
                            "headline": str(art),
                            "summary": "",
                            "timestamp": getattr(ev, "retrieved_at", "").isoformat() if hasattr(ev, "retrieved_at") else "",
                            "url": getattr(ev, "source_url", "")
                        })

        recent_events = await self.event_extractor.execute(entity_name, recent_documents)
        recent_events_serialized = [ev.model_dump() if hasattr(ev, "model_dump") else ev for ev in recent_events]
        ArtifactWriter.write_json("pipeline/4_events.json", {"events": recent_events_serialized})

        # 5. Parallel Section Generation
        logger.info("START Parallel Section Generation")
        
        # Sliced contexts for each section generator
        sections_inputs = {
            "Financials": dict(evidence_graph["financial"]),
            "Technology Intelligence": dict(evidence_graph["technology"]),
            "Competitor Intelligence": dict(evidence_graph["competition"]),
            "Product and Market Intelligence": dict(evidence_graph["products"]),
            "Operations Intelligence": dict(evidence_graph["operations"]),
            "Social Intelligence": dict(evidence_graph["social"]),
            "News and Risk Intelligence": dict(evidence_graph["risk"])
        }
        
        for k in sections_inputs:
            sections_inputs[k]["recent_events"] = recent_events_serialized

        generators = [
            FinancialSectionGenerator(),
            CompetitorSectionGenerator(),
            OperationsSectionGenerator(),
            TechnologySectionGenerator(),
            RiskSectionGenerator(),
            MarketSectionGenerator(),
            SocialSectionGenerator()
        ]
        
        sem_sections = asyncio.Semaphore(2)
        
        async def generate_section(gen, index):
            await asyncio.sleep(index * 0.5)
            async with sem_sections:
                logger.info(f"Launching Section Generator: {gen.section_name}")
                section_input = sections_inputs.get(gen.section_name, {})
                result = await gen.generate(section_input, entity_name)
                return gen.section_name, result
            
        section_tasks = [generate_section(gen, i) for i, gen in enumerate(generators)]
        section_results = await asyncio.gather(*section_tasks)
        
        sections = {}
        for name, result in section_results:
            sections[name] = result
            self.insight_store.save_insight(name, result)
            
        sections_dict = {k: (v.model_dump() if hasattr(v, 'model_dump') else v) for k, v in sections.items()}
        ArtifactWriter.write_json("pipeline/6_sections.json", {"sections": sections_dict})

        # 6. Cross-Provider Reasoning
        logger.info("START Cross-Provider Reasoning")
        await asyncio.sleep(0.5)
        
        cross_reasoning_input = {
            "financial": sections_dict.get("Financials", {}),
            "technology": sections_dict.get("Technology Intelligence", {}),
            "competition": sections_dict.get("Competitor Intelligence", {}),
            "operations": sections_dict.get("Operations Intelligence", {}),
            "products": sections_dict.get("Product and Market Intelligence", {}),
            "social": sections_dict.get("Social Intelligence", {}),
            "risk": sections_dict.get("News and Risk Intelligence", {})
        }
        validated_signals = await self.cross_provider_reasoner.execute(cross_reasoning_input, entity_name)
        
        # 7. Critic Agent Review
        logger.info("START Critic Agent Review")
        await asyncio.sleep(0.5)
        
        present_count = sum(1 for v in sections_dict.values() if v and not all(val == "" or val == {} or val == [] for val in v.values()))
        coverage_data = {
            "coverage_score": round((present_count / len(sections_dict)) * 100, 2) if sections_dict else 100,
            "generated_sections": list(sections_dict.keys())
        }
        citations_data = [
            {"source": getattr(ev, "source", ""), "url": getattr(ev, "source_url", "")}
            for ev in raw_evidence[:20] if getattr(ev, "source_url", "")
        ]

        critic_payload = {
            "sections": sections_dict,
            "signals": validated_signals,
            "coverage": coverage_data,
            "evidence_graph": evidence_graph,
            "citations": citations_data
        }
        critic_result = await self.critic_agent.execute(critic_payload)
        ArtifactWriter.write_json("pipeline/critic_evaluation.json", critic_result.model_dump())
        
        # 7b. Critic Regeneration Loop (1 retry)
        if hasattr(critic_result, "regenerate") and critic_result.regenerate:
            logger.info(f"Critic requested regeneration for: {critic_result.regenerate}")
            regen_tasks = []
            for name in critic_result.regenerate:
                for gen in generators:
                    if gen.section_name == name:
                        section_input = sections_inputs.get(gen.section_name, {})
                        # Inject critic feedback
                        section_input["critic_feedback"] = {
                            "unsupported_claims": critic_result.unsupported_claims,
                            "missing_sections": critic_result.missing_sections
                        }
                        logger.info(f"Relaunching Section Generator: {name}")
                        regen_tasks.append(generate_section(gen, 0))
            if regen_tasks:
                regen_results = await asyncio.gather(*regen_tasks)
                for name, result in regen_results:
                    sections_dict[name] = (result.model_dump() if hasattr(result, 'model_dump') else result)
                    self.insight_store.save_insight(name, result)
                ArtifactWriter.write_json("pipeline/6_sections_retry.json", {"sections": sections_dict})
        
        # 8. Executive Synthesis
        logger.info("START Executive Synthesis")
        await asyncio.sleep(0.5)
        narratives = await self.synthesizer.execute(
            validated_sections=sections_dict,
            validated_signals=validated_signals,
            quality_score=critic_result.quality_score,
            entity_name=entity_name
        )
        for key, text in narratives.items():
            self.narrative_store.save_narrative(key, text)
        ArtifactWriter.write_json("pipeline/7_narratives.json", {"narratives": narratives})
            
        # 9. Page Composer (Deterministic + LLM data binding)
        logger.info("START Page Composer")
        await asyncio.sleep(0.5)
        
        composer_context = {
            "entity": company_entity.model_dump() if hasattr(company_entity, "model_dump") else {"name": entity_name},
            "events": recent_events_serialized,
            "sections": sections_dict,
            "validated_signals": validated_signals,
            "critic_evaluation": critic_result.model_dump(),
            "narratives": narratives,
        }
        
        composed_ui = await self.page_composer.execute(query, composer_context)
        ArtifactWriter.write_json("pipeline/9_ui_generation.json", composed_ui)
        
        final_result = {
            "entity": company_entity.model_dump() if hasattr(company_entity, "model_dump") else {"name": entity_name},
            "events": recent_events_serialized,
            "sections": sections_dict,
            "validated_signals": validated_signals,
            "critic_evaluation": critic_result.model_dump(),
            "narratives": narratives,
            "report_pages": composed_ui.get("report_pages", [])
        }
        
        ArtifactWriter.write_json("final/final_result.json", final_result)
        return final_result

    def _build_scheduler_entity_data(self, company_entity: Any, entity_name: str) -> Dict[str, Any]:
        if company_entity and hasattr(company_entity, "model_dump"):
            entity_data = company_entity.model_dump()
        else:
            entity_data = {}

        entity_core = entity_data.get("entity", {}) if isinstance(entity_data.get("entity"), dict) else {}
        official_pages = entity_data.get("official_pages", {}) if isinstance(entity_data.get("official_pages"), dict) else {}

        entity_data["canonical_name"] = entity_name
        entity_data["company"] = entity_name
        entity_data["company_name"] = entity_name
        entity_data["ticker"] = getattr(company_entity, "ticker", None) or entity_core.get("ticker") or entity_data.get("ticker")
        entity_data["cik"] = getattr(company_entity, "cik", None) or entity_core.get("cik") or entity_data.get("cik")
        entity_data["exchange"] = getattr(company_entity, "exchange", None) or entity_core.get("exchange") or entity_data.get("exchange")
        entity_data["website"] = (
            getattr(company_entity, "website", None)
            or entity_core.get("website")
            or official_pages.get("homepage")
            or official_pages.get("investor_relations")
            or entity_data.get("website")
        )
        entity_data["web_target"] = {
            "company": entity_name,
            "company_name": entity_name,
            "website": entity_data.get("website"),
            "official_pages": official_pages,
            "canonical_name": entity_name,
        }
        return entity_data
