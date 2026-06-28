import logging
from typing import List, Any
from services.knowledge.evidence_store import EvidenceStore
from services.knowledge.evidence import ResearchEvidence
from services.knowledge.confidence_engine import ConfidenceEngine
from services.knowledge.evidence_validator import EvidenceValidator
from services.knowledge.entity_linker import EntityLinker
from services.agents.tool_router_agent import ToolRouterAgent
from services.models.research_execution_plan import ResearchTask

logger = logging.getLogger("uvicorn.error")

class KnowledgeRouter:
    """
    Manages Evidence storage, validation, and cache lookups.
    Dispatches to ToolRouterAgent if cache misses.
    """
    def __init__(self, tool_router: ToolRouterAgent, store: EvidenceStore):
        self.tool_router = tool_router
        self.store = store

    async def get_evidence(self, provider_name: str, target: Any) -> List[ResearchEvidence]:
        """
        Backward compatibility for testing or direct provider calls without a task.
        """
        # Using a dummy task to fulfill the input requirement
        dummy_task = ResearchTask(
            task_id=f"direct_{provider_name}",
            provider_name=provider_name,
            target_field="target"
        )
        return await self.execute_task(dummy_task, target)

    async def execute_task(self, task: ResearchTask, target: Any) -> List[ResearchEvidence]:
        """
        Executes a ResearchTask by first checking the EvidenceStore. 
        If missing or stale, dispatches to ToolRouterAgent.
        """
        provider_name = task.provider_name
        
        # If target is a dictionary/model with a canonical name, we use that for cache lookup.
        # Otherwise fallback to string representation.
        entity_name = str(target)
        if hasattr(target, "company_name") and target.company_name:
            entity_name = target.company_name
        elif isinstance(target, dict) and "company_name" in target:
            entity_name = target["company_name"]
            
        canonical_entity = EntityLinker.canonicalize(entity_name)
        
        # Cache lookup
        existing = self.store.get_all_for_entity(canonical_entity)
        tool_evidence = [e for e in existing if e.source == provider_name]
        
        if tool_evidence:
            logger.info(f"KnowledgeRouter: Cache hit for {canonical_entity} from {provider_name}")
            return tool_evidence
            
        logger.info(f"KnowledgeRouter: Cache miss for {canonical_entity} from {provider_name}. Delegating to ToolRouterAgent.")
        
        raw_data = await self.tool_router.fetch(provider_name, target)
        if not raw_data:
            return []
            
        parsed_evidence = []
        if isinstance(raw_data, list) and all(isinstance(x, ResearchEvidence) for x in raw_data):
            parsed_evidence = raw_data
        elif isinstance(raw_data, ResearchEvidence):
            parsed_evidence = [raw_data]
        else:
            logger.warning(f"KnowledgeRouter: Data from {provider_name} is not ResearchEvidence. Wrapping.")
            base_confidence = ConfidenceEngine.initialize_confidence(provider_name)
            
            from services.knowledge.citation_manager import CitationManager
            attr_name = f"{provider_name}_data"
            ev = ResearchEvidence(
                id=CitationManager.generate_id(provider_name, canonical_entity, attr_name, "current"),
                entity=canonical_entity,
                attribute=attr_name,
                value=raw_data,
                source=provider_name,
                source_type="mcp",
                confidence=base_confidence
            )
            parsed_evidence.append(ev)
            
        EvidenceValidator.validate_group(parsed_evidence)
        
        for ev in parsed_evidence:
            self.store.add_evidence(ev)
            
        # Optional: Dump to disk for visibility
        from services.artifacts.artifact_writer import ArtifactWriter
        try:
            dump_data = [e.model_dump() for e in parsed_evidence]
            safe_entity = canonical_entity.replace(" ", "_").replace("/", "_")
            ArtifactWriter.write_json(f"provider_outputs/{provider_name}_{safe_entity}_evidence.json", dump_data)
        except Exception as e:
            logger.warning(f"Failed to dump parsed evidence for {provider_name}: {e}")
            
        return parsed_evidence
