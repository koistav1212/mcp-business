from typing import Dict, Any, Optional

class InsightStore:
    """
    Stores generated analytical objects for traceability.
    """
    def __init__(self):
        self._insights: Dict[str, Any] = {}

    def save_insight(self, key: str, data: Any):
        self._insights[key] = data

    def get_insight(self, key: str) -> Optional[Any]:
        return self._insights.get(key)

    def get_all(self) -> Dict[str, Any]:
        return self._insights

    def clear(self):
        self._insights.clear()
