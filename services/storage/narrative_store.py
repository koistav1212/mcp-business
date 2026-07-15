from typing import Dict, Optional

class NarrativeStore:
    """
    Persists reusable narratives (e.g. company_summary, investment_case)
    to avoid repeated LLM calls during UI generation and synthesis.
    """
    def __init__(self):
        self._narratives: Dict[str, str] = {}

    def save_narrative(self, key: str, content: str):
        self._narratives[key] = content

    def get_narrative(self, key: str) -> Optional[str]:
        return self._narratives.get(key)

    def get_all(self) -> Dict[str, str]:
        return self._narratives

    def clear(self):
        self._narratives.clear()
