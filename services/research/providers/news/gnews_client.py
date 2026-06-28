import os
import httpx
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

logger = logging.getLogger("uvicorn.error")

class GNewsClient:
    def __init__(self):
        self.api_key = os.getenv("GNEWS_API_KEY")
        self.base_url = "https://gnews.io/api/v4/search"
        
    async def fetch(self, company: str) -> List[Dict[str, Any]]:
        if not self.api_key:
            return []
            
        params = {
            "q": company,
            "lang": "en",
            "country": "us",
            "max": 20,
            "apikey": self.api_key
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
                                dt = datetime.now(timezone.utc)
                                
                        results.append({
                            "headline": art.get("title", ""),
                            "url": art.get("url", ""),
                            "published_at": dt,
                            "publisher": art.get("source", {}).get("name", "GNews")
                        })
        except Exception as e:
            logger.debug(f"GNews fetch failed: {e}")
            
        return results
