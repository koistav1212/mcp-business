from typing import List, Dict, Any
from collections import defaultdict
from services.schemas.insight import BusinessEvent
from difflib import SequenceMatcher

class EventProcessor:
    """
    Algorithmic processing of BusinessEvents.
    Responsible for deduplication, normalization, timeline ordering, and clustering.
    """
    
    @staticmethod
    def process(events: List[BusinessEvent]) -> Dict[str, List[BusinessEvent]]:
        """
        Process raw events and return them clustered by logical groups (e.g. event_type or temporal themes).
        """
        if not events:
            return {}

        # 1. Normalize
        normalized = EventProcessor._normalize(events)
        
        # 2. Deduplicate
        deduped = EventProcessor._deduplicate(normalized)
        
        # 3. Timeline Ordering
        ordered = EventProcessor._order_by_timeline(deduped)
        
        # 4. Clustering (Algorithmic)
        clusters = EventProcessor._cluster(ordered)
        
        return clusters

    @staticmethod
    def _normalize(events: List[BusinessEvent]) -> List[BusinessEvent]:
        # Basic normalization (e.g., lowercasing types, trimming strings)
        for ev in events:
            ev.event_type = ev.event_type.lower().strip().replace(" ", "_")
            ev.headline = ev.headline.strip()
        return events

    @staticmethod
    def _deduplicate(events: List[BusinessEvent], similarity_threshold=0.85) -> List[BusinessEvent]:
        unique_events = []
        for ev in events:
            is_duplicate = False
            for u in unique_events:
                # If same type and headline is very similar, consider it a duplicate
                if ev.event_type == u.event_type:
                    sim = SequenceMatcher(None, ev.headline.lower(), u.headline.lower()).ratio()
                    if sim > similarity_threshold:
                        is_duplicate = True
                        break
            if not is_duplicate:
                unique_events.append(ev)
        return unique_events

    @staticmethod
    def _order_by_timeline(events: List[BusinessEvent]) -> List[BusinessEvent]:
        # Sort by timestamp (assuming ISO format or fallback)
        return sorted(events, key=lambda e: e.timestamp, reverse=True)

    @staticmethod
    def _cluster(events: List[BusinessEvent]) -> Dict[str, List[BusinessEvent]]:
        # Simple clustering by event type for deterministic processing
        clusters = defaultdict(list)
        for ev in events:
            clusters[ev.event_type].append(ev)
        return dict(clusters)
