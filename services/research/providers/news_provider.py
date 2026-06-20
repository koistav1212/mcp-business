import os
import httpx
import email.utils
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from services.research.base import BaseProvider

def classify_article(title: str, snippet: str) -> str:
    text = (title + " " + snippet).lower()
    
    # Check litigation
    if any(kw in text for kw in ["sue", "sued", "lawsuit", "court", "litigation", "ftc", "sec", "antitrust", "investigation", "complaint", "patent", "dispute", "tribunal", "prosecutor"]):
        return "litigation"
    # Check leadership change
    if any(kw in text for kw in ["ceo", "cfo", "cto", "hire", "hired", "appoints", "appointed", "steps down", "leaves", "resigns", "leadership", "executive", "board member"]):
        return "leadership_change"
    # Check acquisition
    if any(kw in text for kw in ["acquire", "acquisition", "bought", "takeover", "merger", "merges", "purchased", "buyout"]):
        return "acquisition"
    # Check investment
    if any(kw in text for kw in ["funding", "raises", "raised", "investment", "invests", "venture capital", "vc", "seed", "series a", "series b", "series c", "funding round"]):
        return "investment"
    # Check earnings
    if any(kw in text for kw in ["earnings", "revenue", "profit", "quarterly", "q1", "q2", "q3", "q4", "fiscal", "financial results", "net income"]):
        return "earnings"
    # Check product launch
    if any(kw in text for kw in ["launch", "announces", "unveils", "introduces", "releases", "presents", "product", "features", "new version", "dlss", "rtx", "chip", "software update"]):
        return "product_launch"
        
    return "general"

class NewsProvider(BaseProvider):
    """
    Fetches real news updates from NewsAPI or Google News RSS and filters/classifies them.
    """

    async def fetch(self, company: str) -> Dict[str, Any]:
        company_clean = company.lower().strip()
        


        # Date boundary: 12 months ago
        now = datetime.now(timezone.utc)
        twelve_months_ago = now - timedelta(days=365)
        
        api_key = os.getenv("NEWS_API_KEY")
        articles_resolved = []
        raw_payload = {}
        source_title = "Google News RSS Feed"
        source_url = f"https://news.google.com/rss/search?q={company_clean}"
        
        if api_key:
            # Sourcing via NewsAPI
            source_title = "NewsAPI Everything Feed"
            from_date_str = twelve_months_ago.strftime("%Y-%m-%d")
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": company,
                "from": from_date_str,
                "sortBy": "publishedAt",
                "apiKey": api_key,
                "language": "en"
            }
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.get(url, params=params, timeout=10.0)
                    if r.status_code == 200:
                        raw_payload = r.json()
                        articles = raw_payload.get("articles", [])
                        for art in articles:
                            published_str = art.get("publishedAt", "")
                            # Parse NewsAPI ISO date
                            try:
                                dt = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                            except Exception:
                                dt = now
                                
                            if dt >= twelve_months_ago:
                                title = art.get("title") or ""
                                snippet = art.get("description") or art.get("content") or ""
                                articles_resolved.append({
                                    "title": title,
                                    "url": art.get("url") or "",
                                    "date": dt.strftime("%Y-%m-%d"),
                                    "snippet": snippet,
                                    "type": classify_article(title, snippet)
                                })
            except Exception as e:
                # Fallback to RSS on error
                raw_payload["news_api_error"] = str(e)
                api_key = None
                
        if not api_key:
            # Sourcing via Google News RSS
            try:
                url = f"https://news.google.com/rss/search?q={company_clean}&hl=en-US&gl=US&ceid=US:en"
                async with httpx.AsyncClient() as client:
                    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                    r = await client.get(url, headers=headers, timeout=10.0)
                    if r.status_code == 200:
                        raw_payload["rss_raw"] = r.text[:10000] # store raw XML snippet
                        root = ET.fromstring(r.content)
                        items = root.findall(".//item")
                        
                        for item in items:
                            title = item.find("title").text if item.find("title") is not None else ""
                            link = item.find("link").text if item.find("link") is not None else ""
                            pub_date_str = item.find("pubDate").text if item.find("pubDate") is not None else ""
                            
                            # Parse RSS date: Fri, 19 Jun 2026 01:09:00 GMT
                            dt = now
                            if pub_date_str:
                                try:
                                    parsed_dt = email.utils.parsedate_to_datetime(pub_date_str)
                                    dt = parsed_dt.astimezone(timezone.utc)
                                except Exception:
                                    pass
                                    
                            if dt >= twelve_months_ago:
                                snippet = title # RSS items don't have separate body description easily
                                articles_resolved.append({
                                    "title": title,
                                    "url": link,
                                    "date": dt.strftime("%Y-%m-%d"),
                                    "snippet": snippet,
                                    "type": classify_article(title, snippet)
                                })
            except Exception as e:
                raw_payload["rss_error"] = str(e)
                
        return {
            "source_title": source_title,
            "source_url": source_url,
            "source_type": "news_outlet",
            "news": articles_resolved,
            "raw_data": raw_payload
        }
