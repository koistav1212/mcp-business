from typing import List, Dict, Any
from datetime import datetime

class TimelineBuilder:
    """
    Sorts events and articles chronologically to build a timeline.
    """
    
    def build(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not articles:
            return []
            
        # Sort by published_at (descending)
        def get_time(a):
            dt = a.get("published_at")
            if isinstance(dt, datetime):
                return dt.timestamp()
            return 0.0
            
        sorted_articles = sorted(articles, key=get_time, reverse=True)
        
        # Assign position in timeline (0 is newest)
        for i, art in enumerate(sorted_articles):
            art["timeline_position"] = i
            
        return sorted_articles
