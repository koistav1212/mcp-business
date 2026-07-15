import asyncio
import re
from urllib.parse import quote
from typing import Any, List, Dict

from crawl4ai import AsyncWebCrawler

from services.research.base import BaseProvider
from services.research.providers.shared_utils import logger


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
        company = self._extract_identifier(target)
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

        # The user requested that we return a dictionary with the "posts" key
        return {"posts": posts}