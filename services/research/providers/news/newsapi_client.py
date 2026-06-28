import os
import httpx
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

logger = logging.getLogger("uvicorn.error")

class NewsAPIClient:
    def __init__(self):
        self.api_key = os.getenv("NEWS_API_KEY")
        self.base_url = "https://newsapi.org/v2/everything"
        
    async def fetch(self, company: str, days_back: int = 30) -> List[Dict[str, Any]]:
        if not self.api_key:
            return []
            
        now = datetime.now(timezone.utc)
        from_date = now - timedelta(days=days_back)
        
        params = {
            "q": company,
            "from": from_date.strftime("%Y-%m-%d"),
            "sortBy": "relevancy",
            "apiKey": self.api_key,
            "language": "en"
        }
        
        results = []
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(self.base_url, params=params, timeout=10.0)
                if resp.status_code == 200:
                    articles = resp.json().get("articles", [])
                    for art in articles:
                        pub_str = art.get("publishedAt", "")
                        dt = None
                        if pub_str:
                            try:
                                dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                            except:
                                dt = now
                                
                        results.append({
                            "headline": art.get("title", ""),
                            "url": art.get("url", ""),
                            "published_at": dt,
                            "publisher": art.get("source", {}).get("name", "NewsAPI")
                        })
        except Exception as e:
            logger.debug(f"NewsAPI fetch failed: {e}")
            
        return results
