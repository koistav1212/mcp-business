from typing import List, Dict, Any
from datetime import datetime

class RelevanceRanker:
    @staticmethod
    def _calculate_recency_score(date_str: str) -> float:
        if not date_str:
            return 0.5
        try:
            parsed = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            days_old = (datetime.now(parsed.tzinfo) - parsed).days
            if days_old <= 1: return 1.0
            if days_old <= 7: return 0.9
            if days_old <= 30: return 0.7
            if days_old <= 90: return 0.5
            return 0.2
        except Exception:
            return 0.5

    @staticmethod
    def _calculate_strategic_impact(text: str) -> float:
        if not text:
            return 0.2
        lowered = text.lower()
        strategic_keywords = ["acquire", "merger", "ceo", "revenue", "lawsuit", "layoff", "launch", "partnership", "earnings", "ipo", "bankruptcy", "funding", "restructuring"]
        score = 0.2
        for kw in strategic_keywords:
            if kw in lowered:
                score += 0.2
        return min(1.0, score)
        
    @staticmethod
    def _calculate_relevance(text: str, entity_name: str) -> float:
        if not text or not entity_name:
            return 0.5
        if entity_name.lower() in text.lower():
            return 1.0
        return 0.5

    @staticmethod
    def rank_news(items: List[Dict[str, Any]], entity_name: str = "") -> List[Dict[str, Any]]:
        scored_items = []
        for item in items:
            val = item.get("value", item) if isinstance(item, dict) else {}
            if not isinstance(val, dict):
                scored_items.append((item, 0.5))
                continue
                
            text = f"{val.get('title', '')} {val.get('snippet', '')}"
            date_str = val.get("date", "")
            
            relevance = RelevanceRanker._calculate_relevance(text, entity_name)
            credibility = item.get("confidence", 0.5) if isinstance(item, dict) else 0.5
            recency = RelevanceRanker._calculate_recency_score(date_str)
            impact = RelevanceRanker._calculate_strategic_impact(text)
            engagement = 0.5 # Default stub
            
            # 0.30 relevance + 0.20 credibility + 0.15 recency + 0.25 strategic impact + 0.10 engagement
            score = (0.30 * relevance) + (0.20 * credibility) + (0.15 * recency) + (0.25 * impact) + (0.10 * engagement)
            
            scored_items.append((item, score))
            
        scored_items.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in scored_items]
