import uuid
from typing import List, Dict, Any, Optional
from services.schemas.insight import BusinessEvent

class EventStore:
    """
    Stores normalized BusinessEvent objects, separating them from raw evidence.
    This enables historical analysis and structured clustering.
    """
    def __init__(self):
        self._events: Dict[str, BusinessEvent] = {}

    def add_event(self, event: BusinessEvent) -> str:
        if not event.id:
            event.id = str(uuid.uuid4())
        self._events[event.id] = event
        return event.id

    def get_event(self, event_id: str) -> Optional[BusinessEvent]:
        return self._events.get(event_id)

    def get_all_events(self) -> List[BusinessEvent]:
        return list(self._events.values())

    def get_events_by_type(self, event_type: str) -> List[BusinessEvent]:
        return [e for e in self._events.values() if e.event_type == event_type]

    def clear(self):
        self._events.clear()
