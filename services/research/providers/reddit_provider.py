import asyncio
import re
from urllib.parse import quote
from typing import Any, List, Dict

from crawl4ai import AsyncWebCrawler

from services.research.base import BaseProvider
from services.research.providers.shared_utils import logger, _write_json


def parse_reddit_markdown(markdown: str) -> List[Dict[str, Any]]:
    """
    Very basic markdown parser to extract potential posts from Reddit search markdown.
    In a real implementation, this would use BeautifulSoup on the HTML or more robust scraping,
    but for this task we extract text chunks separated by common markdown dividers.
    """
    if not markdown:
        return []
        
    posts = []
    # Split by horizontal rules or double newlines to simulate chunks
    chunks = re.split(r'\n\s*\n', markdown)
    
    for i, chunk in enumerate(chunks):
        chunk = chunk.strip()
        if not chunk or len(chunk) < 20:
            continue
            
        posts.append({
            "id": f"post_{i}",
            "body": chunk[:1500],  # Keep reasonable size
            "source": "reddit",
            "url": "https://reddit.com"
        })
        
    return posts


class RedditProvider(BaseProvider):
    """
    Aggregated social & discussion intelligence for a company/ticker using Crawl4AI.
    """

    async def fetch(self, target: Any) -> Dict[str, Any]:
        """
        Entry point: fetch cross-source social intelligence for a given company/ticker.
        """
        company = self._extract_identifier(target, preferred_key="company")
        if not company:
            return {"posts": []}

        company_clean = company.strip()
        logger.info(f"RedditProvider: Fetching raw Reddit posts for '{company_clean}' via Crawl4AI")

        urls = [
            f"https://www.reddit.com/search/?q={quote(company_clean)}",
        ]

        posts = []

        try:
            async with AsyncWebCrawler() as crawler:
                for url in urls:
                    logger.info(f"RedditProvider: Crawling {url}")
                    result = await crawler.arun(url=url)
                    if result and hasattr(result, "markdown"):
                        posts.extend(parse_reddit_markdown(result.markdown))
        except Exception as e:
            logger.exception(f"RedditProvider: Error crawling Reddit: {e}")

        from services.knowledge.evidence import ResearchEvidence
        from services.knowledge.citation_manager import CitationManager

        # The user requested that we return a dictionary with the "posts" key
        result = {"posts": posts}
        _write_json(f"reddit_{company_clean.replace(' ', '_')[:40]}.json", result)
        
        evidence_id = CitationManager.generate_id("social_sentiment", company_clean, "reddit", "current")
        evidence = ResearchEvidence(
            id=evidence_id,
            entity=company_clean,
            attribute="social_sentiment",
            value=result,
            source="reddit",
            source_type="mcp",
            confidence=0.7
        )
        return [evidence]