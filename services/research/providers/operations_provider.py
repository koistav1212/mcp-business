import asyncio
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urljoin

from crawl4ai import AsyncWebCrawler

from services.research.base import BaseProvider
from services.knowledge.evidence import ResearchEvidence
from services.knowledge.citation_manager import CitationManager
from services.research.providers.shared_utils import logger, _write_json


class OperationsProvider(BaseProvider):
    """
    Dedicated Operations Intelligence provider.

    Fills fields for 'Operations Intelligence':
      1. supply_chain
      2. factory
      3. distribution
      4. efficiency
      5. capacity
      6. vendor_risk
    """

    MAX_SNIPPET_CHARS = 1200

    async def fetch(self, target: Any) -> List[ResearchEvidence]:
        company_name = self._resolve_company(target)
        if not company_name:
            logger.warning("OperationsProvider: could not resolve a company name from target")
            return []

        company_key = company_name.strip().lower()
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        evidence_list: List[ResearchEvidence] = []

        async with AsyncWebCrawler() as crawler:
            tasks = [
                self._analyze_supply_chain(crawler, company_name),
                self._analyze_factory(crawler, company_name),
                self._analyze_distribution(crawler, company_name),
                self._analyze_efficiency(crawler, company_name),
                self._analyze_capacity(crawler, company_name),
                self._analyze_vendor_risk(crawler, company_name),
            ]

            results = await asyncio.gather(*tasks)
            supply_chain, factory, distribution, efficiency, capacity, vendor_risk = results

        analyses = [
            ("supply_chain", supply_chain, 0.7),
            ("factory", factory, 0.7),
            ("distribution", distribution, 0.7),
            ("efficiency", efficiency, 0.7),
            ("capacity", capacity, 0.7),
            ("vendor_risk", vendor_risk, 0.7),
        ]

        for attribute, value, confidence in analyses:
            if not value:
                continue
            evidence_id = CitationManager.generate_id(attribute, company_key, "operations_provider", now_str)
            evidence_list.append(
                ResearchEvidence(
                    id=evidence_id,
                    entity=company_key,
                    attribute=attribute,
                    value=value,
                    source="operations_provider",
                    source_type="mcp",
                    confidence=confidence,
                )
            )

        _write_json(
            f"operations_evidence_{company_key.replace(' ', '_')[:40]}.json",
            [e.model_dump(mode="json") for e in evidence_list],
        )
        logger.info(f"OperationsProvider: {len(evidence_list)} evidence items for {company_name}")
        return evidence_list

    async def _safe_crawl(self, crawler: AsyncWebCrawler, url: str) -> str:
        try:
            result = await crawler.arun(url=url)
            markdown = getattr(result, "markdown", "") if result else ""
            return self._clean_text(markdown, limit=self.MAX_SNIPPET_CHARS * 2)
        except Exception as exc:
            logger.warning(f"OperationsProvider: crawl failed for {url} ({exc})")
            return ""

    def _clean_text(self, value: str, limit: int) -> str:
        if not value:
            return ""
        text = re.sub(r"\s+", " ", value).strip()
        if len(text) > limit:
            text = text[: limit - 3].rstrip() + "..."
        return text

    async def _search_topic(self, crawler: AsyncWebCrawler, company_name: str, topic: str) -> Dict[str, Any]:
        query = f"{company_name} {topic}"
        url = f"https://search.yahoo.com/search?p={quote(query)}"
        md = await self._safe_crawl(crawler, url)
        if not md:
            return {}
        return {"summary": md[:self.MAX_SNIPPET_CHARS], "source_url": url}

    async def _analyze_supply_chain(self, crawler: AsyncWebCrawler, company_name: str) -> Dict[str, Any]:
        return await self._search_topic(crawler, company_name, "supply chain logistics strategy")

    async def _analyze_factory(self, crawler: AsyncWebCrawler, company_name: str) -> Dict[str, Any]:
        return await self._search_topic(crawler, company_name, "manufacturing factory locations production")

    async def _analyze_distribution(self, crawler: AsyncWebCrawler, company_name: str) -> Dict[str, Any]:
        return await self._search_topic(crawler, company_name, "distribution network warehouses")

    async def _analyze_efficiency(self, crawler: AsyncWebCrawler, company_name: str) -> Dict[str, Any]:
        return await self._search_topic(crawler, company_name, "operational efficiency cost reduction lean")

    async def _analyze_capacity(self, crawler: AsyncWebCrawler, company_name: str) -> Dict[str, Any]:
        return await self._search_topic(crawler, company_name, "production capacity expansion")

    async def _analyze_vendor_risk(self, crawler: AsyncWebCrawler, company_name: str) -> Dict[str, Any]:
        return await self._search_topic(crawler, company_name, "vendor risk supplier reliance concentration")

    def _resolve_company(self, target: Any) -> Optional[str]:
        if isinstance(target, str):
            return target.strip()
        if isinstance(target, dict):
            company_name = target.get("canonical_name") or target.get("company")
            if not company_name and isinstance(target.get("entity"), dict):
                company_name = target["entity"].get("name")
            return company_name
        return None
