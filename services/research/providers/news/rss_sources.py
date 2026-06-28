import httpx
import logging
import email.utils
from xml.etree import ElementTree as ET
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

logger = logging.getLogger("uvicorn.error")

class RSSCollector:
    """Base class for all RSS-based news collectors."""
    
    def __init__(self, source_name: str, base_url: str):
        self.source_name = source_name
        self.base_url = base_url
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }

    def format_url(self, company: str, ticker: Optional[str] = None) -> str:
        return self.base_url.format(company=company, ticker=ticker)

    async def fetch(self, company: str, ticker: Optional[str] = None) -> List[Dict[str, Any]]:
        url = self.format_url(company, ticker)
        results = []
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(url, headers=self.headers, timeout=10.0)
                if resp.status_code == 200:
                    root = ET.fromstring(resp.content)
                    for item in root.findall(".//item"):
                        title = item.findtext("title", "")
                        link = item.findtext("link", "")
                        pub_date_str = item.findtext("pubDate", "")
                        
                        dt = None
                        if pub_date_str:
                            try:
                                parsed_dt = email.utils.parsedate_to_datetime(pub_date_str)
                                dt = parsed_dt.astimezone(timezone.utc)
                            except Exception:
                                pass
                                
                        if not dt:
                            dt = datetime.now(timezone.utc)
                            
                        results.append({
                            "headline": title,
                            "url": link,
                            "published_at": dt,
                            "publisher": self.source_name
                        })
        except Exception as e:
            logger.debug(f"RSS Fetch failed for {self.source_name} at {url}: {e}")
        return results

class GoogleNewsRSS(RSSCollector):
    def __init__(self):
        super().__init__("Google News", "https://news.google.com/rss/search?q={company}&hl=en-US&gl=US&ceid=US:en")

class YahooFinanceRSS(RSSCollector):
    def __init__(self):
        super().__init__("Yahoo Finance", "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US")

class ReutersRSS(RSSCollector):
    def __init__(self):
        super().__init__("Reuters", "https://www.reutersagency.com/feed/?best-topics=business-finance&type=beta")
        
    def format_url(self, company: str, ticker: Optional[str] = None) -> str:
        # Generic feed, we will filter post-fetch
        return self.base_url

class FinancialTimesRSS(RSSCollector):
    def __init__(self):
        super().__init__("Financial Times", "https://www.ft.com/?format=rss")
        
    def format_url(self, company: str, ticker: Optional[str] = None) -> str:
        return self.base_url
