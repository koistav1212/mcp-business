import asyncio
import logging
from typing import Dict, Any

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
from services.reports.context_builder import InsightPlanner
from services.ui.ui_agent import UIAgent
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
        self.insight_planner = InsightPlanner()
        self.ui_agent = UIAgent()
        
        # Stores
        self.evidence_store = EvidenceStore()
        self.event_store = EventStore()
        self.insight_store = InsightStore()
        self.narrative_store = NarrativeStore()

    async def run(self, query: str) -> Dict[str, Any]:
        ArtifactWriter.write_json("agent_inputs/session_query.json", {"query": query})
        
        # 0. Entity Extraction
        logger.info("START entity_extractor")
        company_entity = await self.entity_extractor.execute(query)
        entity_name = getattr(company_entity, "company", query) if company_entity else query
        ArtifactWriter.write_json("pipeline/1_entity.json", {"entity": entity_name})
        
        # 1. Planning
        logger.info("START planner")
        plan = await self.planner.execute(query, company_entity)
        ArtifactWriter.write_json("pipeline/2_plan.json", {"plan": plan.model_dump() if hasattr(plan, "model_dump") else plan})
        
        # 2. Knowledge Layer (Providers -> Evidence)
        knowledge_router = KnowledgeRouter(self.tool_router, self.evidence_store)
        scheduler = TaskScheduler(knowledge_router)
        logger.info("START mcp_tools via TaskScheduler (Providers -> Evidence)")
        
        entity_data = {"canonical_name": entity_name}
        for provider_name in plan.required_providers:
            await knowledge_router.get_evidence(provider_name, entity_name)
        await scheduler.execute(plan, entity_data)
        
        # We now have raw evidence in self.evidence_store.
        raw_evidence = self.evidence_store.get_all()
        ArtifactWriter.write_json("pipeline/3_evidence.json", {"evidence": [e.model_dump() if hasattr(e, "model_dump") else e for e in raw_evidence]})
        
        # Group evidence by provider for parallel extraction
        evidence_by_provider = {}
        for ev in raw_evidence:
            provider = ev.source or "unknown"
            if provider not in evidence_by_provider:
                evidence_by_provider[provider] = []
            evidence_by_provider[provider].append(ev)

        # 3. Parallel: Provider -> Event Extraction
        logger.info("START Parallel Event Extraction")
        async def extract_events(provider, data):
            events = await self.event_extractor.execute(provider, data, entity_name)
            for ev in events:
                self.event_store.add_event(ev)
            return events
            
        tasks = [extract_events(provider, data) for provider, data in evidence_by_provider.items()]
        await asyncio.gather(*tasks)

        all_events = self.event_store.get_all_events()
        ArtifactWriter.write_json("pipeline/4_events.json", {"events": [e.model_dump() if hasattr(e, "model_dump") else e for e in all_events]})

        # 4. Deterministic: Event Processing / Clustering
        logger.info("START Deterministic Event Processing")
        clusters = EventProcessor.process(all_events)
        
        # 5. Sequential: Theme Detection
        logger.info("START Theme Detection")
        themes = await self.theme_detector.execute(clusters)
        ArtifactWriter.write_json("pipeline/5_themes.json", {"themes": themes})
        
        # Build context object for Section Generators (simplified mapping from events/themes)
        context_for_sections = {
            "events": [e.model_dump() for e in all_events],
            "themes": themes,
            "raw_evidence": [e.model_dump() for e in raw_evidence]
        }

        # 6. Parallel: Section Generation
        logger.info("START Parallel Section Generation")
        generators = [
            FinancialSectionGenerator(),
            CompetitorSectionGenerator(),
            OperationsSectionGenerator(),
            TechnologySectionGenerator(),
            RiskSectionGenerator(),
            MarketSectionGenerator(),
            SocialSectionGenerator()
        ]
        
        async def generate_section(gen):
            result = await gen.generate(context_for_sections, entity_name)
            return gen.section_name, result
            
        section_tasks = [generate_section(gen) for gen in generators]
        section_results = await asyncio.gather(*section_tasks)
        
        sections = {}
        for name, result in section_results:
            sections[name] = result
            self.insight_store.save_insight(name, result)
        ArtifactWriter.write_json("pipeline/6_sections.json", {"sections": {k: (v.model_dump() if hasattr(v, 'model_dump') else v) for k, v in sections.items()}})

        # 7. Sequential: Cross-Provider Reasoning
        logger.info("START Cross-Provider Reasoning")
        validated_signals = await self.cross_provider_reasoner.execute(sections, entity_name)
        
        # 8. Sequential: Executive Synthesis (Populates NarrativeStore)
        logger.info("START Executive Synthesis")
        narratives = await self.synthesizer.execute(sections, validated_signals, entity_name)
        for key, text in narratives.items():
            self.narrative_store.save_narrative(key, text)
        ArtifactWriter.write_json("pipeline/7_narratives.json", {"narratives": narratives})
            
        # 9. UI Generation: Insight Planner -> UI Agent
        logger.info("START Insight Planner")
        ui_plan = await self.insight_planner.plan(sections, narratives, entity_name)
        ArtifactWriter.write_json("pipeline/8_ui_plan.json", {"ui_plan": ui_plan})
        
        logger.info("START UIAgent (Page Composer)")
        ui_generation = await self.ui_agent.execute(query, {"sections": sections, "narratives": narratives}, ui_plan)
        ArtifactWriter.write_json("pipeline/9_ui_generation.json", ui_generation)
        
        # Assemble final result matching ResearchContext for backward compatibility if needed, or structured JSON
        final_result = {
            "entity": {"name": entity_name},
            "events": [e.model_dump() for e in all_events],
            "themes": themes,
            "sections": {k: (v.model_dump() if hasattr(v, 'model_dump') else v) for k, v in sections.items()},
            "validated_signals": validated_signals,
            "narratives": narratives,
            "ui_plan": ui_plan,
            "ui_generation": ui_generation.get("ui_generation", [])
        }
        
        ArtifactWriter.write_json("final/final_result.json", final_result)
        return final_result
