import logging
from typing import Optional, Any, List
from .evidence_store import EvidenceStore
from .evidence import ResearchEvidence
from .confidence_engine import ConfidenceEngine
from .evidence_validator import EvidenceValidator
from .entity_linker import EntityLinker
from services.agents.tool_router_agent import ToolRouterAgent

logger = logging.getLogger("uvicorn.error")

class KnowledgeRouter:
    """
    Smart router that intercepts requests, checks EvidenceStore first, 
    and delegates to ToolRouterAgent if data is missing or stale.
    """
    def __init__(self, tool_router: ToolRouterAgent, store: EvidenceStore):
        self.tool_router = tool_router
        self.store = store

    async def get_evidence(self, tool_name: str, entity_name: str) -> List[ResearchEvidence]:
        """
        Retrieves evidence for a specific entity from a specific tool/domain.
        If not in store, it calls ToolRouterAgent, normalizes the output, and stores it.
        """
        canonical_entity = EntityLinker.canonicalize(entity_name)
        
        # In a fully granular system, we would ask for specific attributes (e.g. "Revenue").
        # For now, we simulate by checking if we have ANY evidence for this entity/tool combo.
        # Since EvidenceStore indexes by attribute, we'll just check if the entity exists 
        # and has evidence from this tool (source).
        existing = self.store.get_all_for_entity(canonical_entity)
        tool_evidence = [e for e in existing if e.source == tool_name]
        
        if tool_evidence:
            logger.info(f"KnowledgeRouter: Cache hit for {canonical_entity} from {tool_name}")
            return tool_evidence
            
        logger.info(f"KnowledgeRouter: Cache miss for {canonical_entity} from {tool_name}. Delegating to ToolRouterAgent.")
        
        # Delegate to ToolRouterAgent to actually call the MCP
        # Target might need to be canonicalized or mapped based on the tool (e.g., CIK vs Ticker).
        # We assume the caller handles that mapping before calling this, or ToolRouter handles it.
        raw_data = await self.tool_router.fetch(tool_name, canonical_entity)
        
        if not raw_data:
            return []
            
        # Here we would normally parse raw_data into ResearchEvidence subclasses.
        # Since we are gradually migrating, we will yield a generic ResearchEvidence for now,
        # or rely on the MCP providers to return properly formatted Evidence objects.
        
        # If the MCP provider returned a list of ResearchEvidence objects:
        parsed_evidence = []
        if isinstance(raw_data, list) and len(raw_data) > 0:
            logger.info(f"KnowledgeRouter debug: type of raw_data[0] = {type(raw_data[0])}")
            logger.info(f"KnowledgeRouter debug: expected ResearchEvidence = {ResearchEvidence}")
            logger.info(f"KnowledgeRouter debug: isinstance = {isinstance(raw_data[0], ResearchEvidence)}")

        if isinstance(raw_data, list) and all(isinstance(x, ResearchEvidence) for x in raw_data):
            parsed_evidence = raw_data
        elif isinstance(raw_data, ResearchEvidence):
            parsed_evidence = [raw_data]
        else:
            # Fallback wrapper if provider hasn't been updated yet
            logger.warning(f"KnowledgeRouter: Data from {tool_name} is not ResearchEvidence. Wrapping.")
            base_confidence = ConfidenceEngine.initialize_confidence(tool_name)
            
            from .citation_manager import CitationManager
            import datetime
            
            # Create a generic piece of evidence
            attr_name = f"{tool_name}_data"
            ev = ResearchEvidence(
                id=CitationManager.generate_id(tool_name, canonical_entity, attr_name, "current"),
                entity=canonical_entity,
                attribute=attr_name,
                value=raw_data,
                source=tool_name,
                source_type="mcp",
                confidence=base_confidence
            )
            parsed_evidence.append(ev)
            
        # Validate and store
        EvidenceValidator.validate_group(parsed_evidence)
        
        for ev in parsed_evidence:
            self.store.add_evidence(ev)
            
        return parsed_evidence
