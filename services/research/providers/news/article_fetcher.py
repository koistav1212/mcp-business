import asyncio
import httpx
import logging
from typing import List, Dict, Any

logger = logging.getLogger("uvicorn.error")

class ArticleFetcher:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }

    async def _fetch_single(self, client: httpx.AsyncClient, item: Dict[str, Any]) -> Dict[str, Any]:
        url = item.get("url")
        if not url:
            return item
            
        try:
            resp = await client.get(url, headers=self.headers, timeout=12.0)
            if resp.status_code == 200:
                item["html"] = resp.text
            else:
                item["html"] = None
        except Exception as e:
            logger.debug(f"Failed to fetch HTML for {url}: {e}")
            item["html"] = None
            
        return item

    async def fetch_all(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Takes a list of dictionaries (which must contain a 'url' key)
        and fetches the HTML for each, adding an 'html' key to the dictionary.
        """
        async with httpx.AsyncClient(follow_redirects=True) as client:
            tasks = [self._fetch_single(client, art) for art in articles]
            results = await asyncio.gather(*tasks)
            
        return results
