from typing import List, Dict, Any
from services.intelligence.deduplicator import Deduplicator
from services.intelligence.relevance_ranker import RelevanceRanker
from services.intelligence.event_clusterer import EventClusterer
from services.intelligence.decision_ranker import DecisionRanker

class EvidenceDistiller:

    @staticmethod
    def _unwrap_item(item: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(item, dict):
            return {}
        value = item.get("value")
        if isinstance(value, dict):
            result = dict(value)
            result["_source_ids"] = item.get("source_ids", [])
            result["_confidence"] = item.get("confidence", 0.0)
            return result
        return dict(item)

    @staticmethod
    def _rewrap_item(item: Dict[str, Any]) -> Dict[str, Any]:
        source_ids = item.pop("_source_ids", [])
        confidence = item.pop("_confidence", 0.0)
        return {
            "value": item,
            "source_ids": source_ids,
            "confidence": confidence,
        }

    @classmethod
    def distill_news(cls, news_items: List[Dict[str, Any]], entity_name: str, max_items: int = 10) -> List[Dict[str, Any]]:
        if not news_items:
            return []
        normalized = [cls._unwrap_item(item) for item in news_items]
        normalized = [item for item in normalized if item.get("title") or item.get("headline")]
        if not normalized:
            return []
        deduped = Deduplicator.deduplicate(normalized, url_key="url", title_key="title")
        clustered = EventClusterer.cluster_events(deduped)
        ranked = RelevanceRanker.rank_news(clustered, entity_name)
        decision_ranked = DecisionRanker.rank_decisions(ranked)
        selected = decision_ranked[:max_items]
        return [cls._rewrap_item(dict(item)) for item in selected]

    @classmethod
    def distill_collection(cls, items: List[Dict[str, Any]], entity_name: str, max_items: int = 10, title_key: str = "title") -> List[Dict[str, Any]]:
        if not items:
            return []
        normalized = [cls._unwrap_item(item) for item in items]
        normalized = [item for item in normalized if item]
        if not normalized:
            return []
        deduped = Deduplicator.deduplicate(normalized, url_key="url", title_key=title_key)
        ranked = RelevanceRanker.rank_news(deduped, entity_name)
        selected = ranked[:max_items]
        return [cls._rewrap_item(dict(item)) for item in selected]

    @classmethod
    def distill_risks(cls, items: List[Dict[str, Any]], max_items: int = 8) -> List[Dict[str, Any]]:
        normalized = []
        for item in items:
            value = item.get("value")
            if isinstance(value, str):
                normalized.append({
                    "risk": value,
                    "_source_ids": item.get("source_ids", []),
                    "_confidence": item.get("confidence", 0.0),
                })
            elif isinstance(value, dict):
                normalized.append({
                    **value,
                    "_source_ids": item.get("source_ids", []),
                    "_confidence": item.get("confidence", 0.0),
                })
        ranked = DecisionRanker.rank_risks(normalized)
        return [
            {
                "value": {k: v for k, v in risk.items() if not k.startswith("_")},
                "source_ids": risk.get("_source_ids", []),
                "confidence": risk.get("_confidence", 0.0),
            }
            for risk in ranked[:max_items]
        ]
