from typing import Dict, Optional

class EntityLinker:
    """
    Canonicalizes entities to ensure variants map to a single entity ID.
    Example: Apple, AAPL, Apple Inc. -> AAPL
    """
    _ALIASES: Dict[str, str] = {
        "apple": "AAPL",
        "apple inc": "AAPL",
        "apple inc.": "AAPL",
        "aapl": "AAPL",
        "microsoft": "MSFT",
        "microsoft corp": "MSFT",
        "msft": "MSFT"
    }

    @classmethod
    def canonicalize(cls, entity_name: str) -> str:
        if not entity_name:
            return "UNKNOWN"
        normalized = entity_name.lower().strip()
        return cls._ALIASES.get(normalized, entity_name)

    @classmethod
    def add_alias(cls, alias: str, canonical_id: str):
        cls._ALIASES[alias.lower().strip()] = canonical_id
