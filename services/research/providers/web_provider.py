import asyncio
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from crawl4ai import AsyncWebCrawler

from services.research.base import BaseProvider
from services.knowledge.evidence import ResearchEvidence
from services.knowledge.citation_manager import CitationManager
from services.research.providers.shared_utils import _write_json, logger
from services.llm.provider_router import ProviderRouter
import json


class WebProvider(BaseProvider):
    """
    Website Provider (Main Source)
    Aggregates intelligence for a company by crawling its public web presence using crawl4ai.
    """

    async def fetch(self, target: Any) -> List[ResearchEvidence]:
        company = self._extract_identifier(target)
        if not company:
            return []

        company_clean = company.strip()
        company_key = company_clean.lower()

        evidence_list: List[ResearchEvidence] = []

        # 1) Discover base URL
        base_url = self._guess_company_url(company_clean)
        logger.info(f"WebProvider: guessed base URL '{base_url}' for company '{company_clean}'")

        if not base_url:
            return []

        # 2) Define the pages to crawl based on the user's requirement
        pages_to_check = [
            "/", "/products", "/solutions", "/industries", "/pricing", 
            "/blog", "/docs", "/case-studies", "/developers", "/about", 
            "/investors", "/press", "/careers"
        ]

        crawled_markdown = []
        
        # We will crawl sequentially or concurrently with a limit. For now, concurrently.
        async with AsyncWebCrawler() as crawler:
            async def fetch_page(path: str):
                url = urljoin(base_url, path)
                try:
                    result = await crawler.arun(url=url)
                    if result and result.markdown:
                        logger.info(f"WebProvider: successfully crawled {url}")
                        return result.markdown
                except Exception as e:
                    logger.warning(f"WebProvider: error crawling {url} ({e})")
                return ""

            # Concurrently fetch pages
            tasks = [fetch_page(path) for path in pages_to_check]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for res in results:
                if isinstance(res, str) and res:
                    crawled_markdown.append(res)

        combined_text = "\n".join(crawled_markdown)
        
        if not combined_text.strip():
            logger.warning(f"WebProvider: No content extracted for {company_clean}.")
            return []

        # 3) Extract structured entities using LLM
        system_prompt = (
            "You are an expert Business Intelligence Analyst.\n"
            "Extract comprehensive information from the provided website markdown.\n"
            "Return a JSON object containing EXACTLY these keys with arrays of strings as values:\n"
            "Products, Services, Technologies, Integrations, Features, Customers, Partners, Industries, Use_Cases.\n"
            "If no information is found for a category, return an empty array. Do not hallucinate."
        )

        # Truncate to a reasonable length for the LLM
        max_chars = 30000 
        truncated_text = combined_text[:max_chars]
        
        user_prompt = f"Company website markdown:\n{truncated_text}\n\nExtract the required entities in JSON format."

        extracted_data = {}
        try:
            parsed = await ProviderRouter.generate_json(
                agent_name="technology_agent", # using an existing agent configuration
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            extracted_data = {
                "Products": parsed.get("Products", []),
                "Services": parsed.get("Services", []),
                "Technologies": parsed.get("Technologies", []),
                "Integrations": parsed.get("Integrations", []),
                "Features": parsed.get("Features", []),
                "Customers": parsed.get("Customers", []),
                "Partners": parsed.get("Partners", []),
                "Industries": parsed.get("Industries", []),
                "Use_Cases": parsed.get("Use_Cases", [])
            }
        except Exception as e:
            logger.warning(f"WebProvider LLM extraction failed: {e}")
            return []

        # 4) Emit ResearchEvidence
        evidence_id = CitationManager.generate_id(
            "website_intelligence",
            company_key,
            "website",
            "current",
        )
        
        evidence_list.append(
            ResearchEvidence(
                id=evidence_id,
                entity=company_key,
                attribute="website_intelligence",
                value=extracted_data,
                source="company_website",
                source_type="mcp",
                confidence=0.8,
            )
        )

        _write_json(
            f"web_evidence_{company_key.replace(' ', '_')[:40]}.json",
            [e.model_dump(mode="json") for e in evidence_list],
        )

        return evidence_list

    def _guess_company_url(self, company: str) -> Optional[str]:
        """
        Very naive URL guesser.
        """
        token = company.lower().replace(" ", "")
        if not token:
            return None
        return f"https://{token}.com"
