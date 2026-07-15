import json
import logging
from typing import List, Any
import uuid
import httpx

from services.schemas.insight import BusinessEvent
from core.config import settings

logger = logging.getLogger("uvicorn.error")

class EventExtractorAgent:
    """
    Takes raw evidence (from a specific provider) and extracts canonical BusinessEvent objects
    using an LLM.
    """
    async def execute(self, provider_name: str, raw_evidence: List[Any], entity_name: str) -> List[BusinessEvent]:
        if not raw_evidence:
            return []

        # We'll batch evidence or send a summary to avoid token limits, but for now we format it as JSON
        evidence_json = json.dumps([getattr(e, 'value', e) for e in raw_evidence[:20]], default=str)
        
        system_instruction = (
            "You are an expert business analyst. Your task is to extract structured BusinessEvent objects "
            f"for the company {entity_name} from the provided raw data from provider '{provider_name}'.\n"
            "Emit a JSON list of objects, each with: 'event_type' (e.g. 'product_launch', 'hiring', 'earnings', 'lawsuit'), "
            "'headline', 'summary', 'timestamp', and optional 'metrics' (dict). "
            "Do not hallucinate. Only extract events explicitly mentioned in the text."
        )

        prompt = f"Extract events from this raw data:\n{evidence_json}"
        try:
            from services.llm.provider_router import ProviderRouter
            parsed = await ProviderRouter.generate_json(
                agent_name="event_extractor",
                system_prompt=system_instruction,
                user_prompt=prompt
            )
            events_list = parsed.get("events", [])
            
            business_events = []
            for ev in events_list:
                business_events.append(
                    BusinessEvent(
                        id=ev.get("id", ""),
                        source_id=ev.get("source_id", ""),
                        provider=provider_name,
                        timestamp=ev.get("timestamp", ""),
                        event_type=ev.get("event_type", ""),
                        entity=entity_name,
                        headline=ev.get("headline", ""),
                        summary=ev.get("summary", ""),
                        metrics=ev.get("metrics", {}),
                        confidence=ev.get("confidence", 0.0)
                    )
                )
            return business_events
        except Exception as e:
            logger.error(f"EventExtractorAgent failed for {provider_name}: {e}")
            return []
