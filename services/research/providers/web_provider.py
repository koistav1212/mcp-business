import asyncio
import json
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from crawl4ai import AsyncWebCrawler

from services.knowledge.citation_manager import CitationManager
from services.knowledge.evidence import ResearchEvidence
from services.research.base import BaseProvider
from services.research.providers.shared_utils import _write_json, logger

class WebProvider(BaseProvider):
    """
    Crawl a company's public website and return structured page snippets.
    """

    PAGES_TO_CHECK = [
        "/",
        "/products",
        "/solutions",
        "/industries",
        "/pricing",
        "/blog",
        "/docs",
        "/case-studies",
        "/developers",
        "/about",
        "/investors",
        "/press",
        "/careers",
    ]
    MAX_SNIPPET_CHARS = 1800
    MAX_TOTAL_CHARS = 10000

    async def fetch(self, target: Any) -> List[ResearchEvidence]:
        company_name, base_url = self._resolve_company_and_base_url(target)
        if not company_name and not base_url:
            logger.warning("WebProvider: could not resolve a company name or website from target")
            return []

        company_label = company_name or self._hostname_label(base_url) or "unknown_company"
        company_key = company_label.strip().lower()

        if not base_url:
            logger.warning(f"WebProvider: no resolvable base URL for {company_label}")
            return []

        logger.info(f"WebProvider: using base URL '{base_url}' for company '{company_label}'")
        page_context = await self._crawl_pages(base_url, company_label)
        if not page_context:
            logger.warning(f"WebProvider: no crawlable content extracted for {company_label} from {base_url}")
            return []

        extracted_data = {"pages": page_context}

        evidence_id = CitationManager.generate_id(
            "website_intelligence",
            company_key,
            "website",
            "current",
        )
        evidence = ResearchEvidence(
            id=evidence_id,
            entity=company_key,
            attribute="website_intelligence",
            value=extracted_data,
            source="company_website",
            source_type="mcp",
            confidence=0.8,
            metadata={
                "base_url": base_url,
                "pages_crawled": len(page_context),
                "paths": [page["path"] for page in page_context],
            },
        )

        _write_json(
            f"web_evidence_{company_key.replace(' ', '_')[:40]}.json",
            [evidence.model_dump(mode="json")],
        )
        return [evidence]

    async def _crawl_pages(self, base_url: Optional[str], company_label: str) -> List[Dict[str, str]]:
        async with AsyncWebCrawler() as crawler:
            async def fetch_url(url: str, path_label: str) -> Optional[Dict[str, str]]:
                try:
                    result = await crawler.arun(url=url)
                except Exception as exc:
                    logger.warning(f"WebProvider: error crawling {url} ({exc})")
                    return None

                markdown = getattr(result, "markdown", "") if result else ""
                cleaned_markdown = self._clean_markdown(markdown)
                if not cleaned_markdown:
                    return None

                logger.info(f"WebProvider: successfully crawled {url}")
                return {
                    "path": path_label,
                    "url": url,
                    "snippet": cleaned_markdown[: self.MAX_SNIPPET_CHARS],
                }

            urls_to_fetch = []
            if base_url:
                for p in self.PAGES_TO_CHECK:
                    urls_to_fetch.append((urljoin(base_url, p), p))
            
            if company_label and company_label != "unknown_company":
                wiki_url = f"https://en.wikipedia.org/wiki/{company_label.replace(' ', '_')}"
                urls_to_fetch.append((wiki_url, "/wikipedia"))

            tasks = [fetch_url(u, p) for u, p in urls_to_fetch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        page_context: List[Dict[str, str]] = []
        total_chars = 0
        for result in results:
            if isinstance(result, Exception) or not result:
                continue
            snippet = result["snippet"]
            if total_chars >= self.MAX_TOTAL_CHARS:
                break
            remaining = self.MAX_TOTAL_CHARS - total_chars
            if len(snippet) > remaining:
                result = dict(result)
                result["snippet"] = snippet[:remaining].rstrip() + "..."
            page_context.append(result)
            total_chars += len(result["snippet"])
        return page_context



    def _resolve_company_and_base_url(self, target: Any) -> Tuple[Optional[str], Optional[str]]:
        if isinstance(target, str):
            if self._looks_like_url(target):
                return self._hostname_label(target), self._normalize_base_url(target)
            company_name = target.strip()
            return company_name, self._guess_company_url(company_name)

        company_name = self._extract_identifier(target, preferred_key="company")
        website = self._extract_url_hint(target)
        if website:
            return company_name, self._normalize_base_url(website)
        if company_name:
            return company_name, self._guess_company_url(company_name)
        return None, None

    def _extract_url_hint(self, target: Any) -> Optional[str]:
        if not isinstance(target, dict):
            return None

        direct_fields = [
            target.get("website"),
            target.get("official_website"),
            target.get("homepage"),
            target.get("canonical_domain"),
        ]
        entity = target.get("entity", {}) if isinstance(target.get("entity"), dict) else {}
        official_pages = target.get("official_pages", {}) if isinstance(target.get("official_pages"), dict) else {}
        direct_fields.extend(
            [
                entity.get("website"),
                entity.get("canonical_domain"),
                official_pages.get("homepage"),
                official_pages.get("about"),
            ]
        )

        for value in direct_fields:
            if value and self._looks_like_url(str(value)):
                return str(value)
        return None

    def _normalize_base_url(self, value: str) -> str:
        raw_value = value.strip()
        if not raw_value.startswith(("http://", "https://")):
            raw_value = f"https://{raw_value}"
        parsed = urlparse(raw_value)
        if not parsed.netloc:
            return raw_value.rstrip("/")
        return f"{parsed.scheme}://{parsed.netloc}/"

    def _looks_like_url(self, value: str) -> bool:
        value = value.strip().lower()
        return value.startswith(("http://", "https://")) or ("." in value and " " not in value and "/" not in value[:1])

    def _hostname_label(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        parsed = urlparse(value if value.startswith(("http://", "https://")) else f"https://{value}")
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        if not host:
            return None
        return host.split(".")[0].replace("-", " ")



    def _clean_markdown(self, markdown: str) -> str:
        if not markdown:
            return ""
        text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", markdown)
        text = re.sub(r"\[[^\]]+\]\([^)]+\)", " ", text)
        text = re.sub(r"`{1,3}", " ", text)
        text = re.sub(r"[#>*_\-]{2,}", " ", text)
        return self._clean_text(text, self.MAX_SNIPPET_CHARS * 2)

    def _clean_text(self, value: str, limit: int) -> str:
        text = re.sub(r"\s+", " ", value).strip()
        if len(text) > limit:
            text = text[: limit - 3].rstrip() + "..."
        return text

    def _guess_company_url(self, company: str) -> Optional[str]:
        token = re.sub(r"[^a-z0-9]", "", company.lower())
        if not token:
            return None
        return f"https://{token}.com/"
