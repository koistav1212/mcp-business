import json
import logging
from typing import Any, Dict, List, Optional
from services.schemas.insight import NewBusinessEvent

logger = logging.getLogger("uvicorn.error")

EVENT_EXTRACTION_SYSTEM_PROMPT = """You are a Business Event Extraction Agent.
Identify material events (such as product launches, leadership changes, major regulatory updates, earnings announcements) for the target company from the provided list of recent documents.
For each event, determine the type, calculate an importance score (0.0 to 1.0), and extract key details.

Return ONLY a valid JSON object matching the requested schema. Do not include extra text or markdown formatting.

Output schema:
{
  "events": [
    {
      "type": "Product Launch",
      "importance": 0.92,
      "headline": "headline description",
      "date": "timestamp",
      "entities": ["entity1", "entity2"],
      "metrics": ["extracted metric values"],
      "evidence_ids": ["source document urls or ids"]
    }
  ]
}
"""

class EventExtractorAgent:
    """
    Refactored Event Extractor Agent matching the new structured query contract.
    Processes recent documents only, classifying events with an LLM.
    """

    def supports_provider(self, provider_name: str) -> bool:
        return True

    async def execute(self, entity_name: str, recent_documents: List[Dict[str, Any]]) -> List[NewBusinessEvent]:
        if not recent_documents:
            logger.warning("EventExtractorAgent: No recent documents provided.")
            return []

        prompt_context = {
            "entity": entity_name,
            "recent_documents": recent_documents[:15]  # Limit to top 15 recent documents to keep prompt token-efficient
        }

        try:
            from services.llm.provider_router import ProviderRouter
            
            payload_str = json.dumps(prompt_context, default=str)
            logger.info(
                "EventExtractor -> documents=%d chars=%d",
                len(prompt_context["recent_documents"]),
                len(payload_str)
            )

            parsed = await ProviderRouter.generate_json(
                agent_name="event_extractor",
                system_prompt=EVENT_EXTRACTION_SYSTEM_PROMPT,
                user_prompt=payload_str,
            )
            
            events_list = parsed if isinstance(parsed, list) else parsed.get("events", [])
            return [NewBusinessEvent.model_validate(ev) for ev in events_list]
        except Exception as exc:
            logger.error(f"EventExtractorAgent execution failed: {exc}")
            return []
