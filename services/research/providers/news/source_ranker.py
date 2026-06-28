from typing import List, Dict, Any

class SourceRanker:
    """
    Assigns credibility scores based on the publisher.
    """
    
    # Base source multipliers
    SOURCE_WEIGHTS = {
        "reuters": 1.0,
        "bloomberg": 1.0,
        "sec": 1.0,
        "investor relations": 1.0,
        "financial times": 0.95,
        "wsj": 0.95,
        "cnbc": 0.9,
        "yahoo finance": 0.8,
        "marketwatch": 0.8,
        "google news": 0.7,
        "seeking alpha": 0.6,
        "motley fool": 0.6,
        "benzinga": 0.5,
        "reddit": 0.3,
        "hackernews": 0.3
    }

    def rank(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for art in articles:
            publisher = art.get("publisher", "").lower()
            
            score = 0.5 # Default medium score
            for src, weight in self.SOURCE_WEIGHTS.items():
                if src in publisher:
                    score = weight
                    break
                    
            art["source_score"] = score
            
        return articles
