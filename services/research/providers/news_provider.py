import os
import httpx
import email.utils
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from services.research.base import BaseProvider
from services.knowledge.evidence import ResearchEvidence
from services.knowledge.citation_manager import CitationManager

def classify_article(title: str, snippet: str) -> str:
    text = (title + " " + snippet).lower()
    if any(kw in text for kw in ["sue", "sued", "lawsuit", "court", "litigation", "ftc", "sec", "antitrust", "investigation"]): return "litigation"
    if any(kw in text for kw in ["ceo", "cfo", "cto", "hire", "hired", "appoints", "leadership"]): return "leadership_change"
    if any(kw in text for kw in ["acquire", "acquisition", "bought", "takeover", "merger"]): return "acquisition"
    if any(kw in text for kw in ["funding", "raises", "investment", "vc", "seed", "series"]): return "investment"
    if any(kw in text for kw in ["earnings", "revenue", "profit", "quarterly", "fiscal"]): return "earnings"
    if any(kw in text for kw in ["launch", "announces", "unveils", "product", "features"]): return "product_launch"
    return "general"

class NewsProvider(BaseProvider):
    """
    Fetches real news updates from NewsAPI or Google News RSS.
    Returns typed ResearchEvidence lists.
    """

    async def fetch(self, target: Any) -> List[ResearchEvidence]:
        company = self._extract_identifier(target)
        if not company:
            return []
            
        company_clean = company.lower().strip()
        now = datetime.now(timezone.utc)
        twelve_months_ago = now - timedelta(days=365)
        
        api_key = os.getenv("NEWS_API_KEY")
        articles_resolved = []
        
        if api_key:
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
                        articles = r.json().get("articles", [])
                        for art in articles:
                            published_str = art.get("publishedAt", "")
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
                api_key = None
                
        if not api_key:
            try:
                url = f"https://news.google.com/rss/search?q={company_clean}&hl=en-US&gl=US&ceid=US:en"
                async with httpx.AsyncClient() as client:
                    headers = {"User-Agent": "Mozilla/5.0"}
                    r = await client.get(url, headers=headers, timeout=10.0)
                    if r.status_code == 200:
                        root = ET.fromstring(r.content)
                        items = root.findall(".//item")
                        
                        for item in items:
                            title = item.find("title").text if item.find("title") is not None else ""
                            link = item.find("link").text if item.find("link") is not None else ""
                            pub_date_str = item.find("pubDate").text if item.find("pubDate") is not None else ""
                            
                            dt = now
                            if pub_date_str:
                                try:
                                    parsed_dt = email.utils.parsedate_to_datetime(pub_date_str)
                                    dt = parsed_dt.astimezone(timezone.utc)
                                except Exception:
                                    pass
                                    
                            if dt >= twelve_months_ago:
                                articles_resolved.append({
                                    "title": title,
                                    "url": link,
                                    "date": dt.strftime("%Y-%m-%d"),
                                    "snippet": title,
                                    "type": classify_article(title, title)
                                })
            except Exception as e:
                pass
                
        evidence_list = []
        for idx, art in enumerate(articles_resolved):
            evidence_list.append(ResearchEvidence(
                id=CitationManager.generate_id("news_feed", company_clean, f"news_article_{idx}", art['date']),
                entity=company_clean,
                attribute="news",
                value=art,
                source="news_feed",
                source_type="mcp",
                confidence=0.8,
                freshness=art['date']
            ))
            
        return evidence_list
