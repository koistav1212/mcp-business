import asyncio
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup  # pip install beautifulsoup4

from services.research.base import BaseProvider
from services.knowledge.evidence import ResearchEvidence
from services.knowledge.citation_manager import CitationManager
from services.research.providers.shared_utils import _write_json, BROWSER_HEADERS, logger
from services.llm.provider_router import ProviderRouter
import json


class WebProvider(BaseProvider):
    """
    Aggregates technology and architecture intelligence for a company by
    crawling its public web presence and building a structured technology profile.

    Data sources (first pass):
      - Company website (home, /careers, /jobs if present)
      - Linked GitHub org/user (if found on the site)

    Outputs:
      - technology_profile: compact domain-specific categories (e.g., languages, ai_frameworks, cloud)
      - technology_intelligence: broader technology-intel categories (core_platforms,
        programming_languages, frontend_frameworks, backend_frameworks, ai_ml_frameworks,
        cloud_providers, databases, data_engineering, containerization, orchestration,
        ci_cd, monitoring, security, cdn, api_technologies, mobile_technologies, web_servers)
    """

    async def fetch(self, target: Any) -> List[ResearchEvidence]:
        company = self._extract_identifier(target)
        if not company:
            return []

        company_clean = company.strip()
        company_key = company_clean.lower()

        evidence_list: List[ResearchEvidence] = []

        # ------------------------------------------------------------------
        # 1) Discover base URL(s) for crawling
        # ------------------------------------------------------------------
        base_url = self._guess_company_url(company_clean)
        logger.info("WebProvider: guessed base URL '%s' for company '%s'", base_url, company_clean)

        if not base_url:
            # If we can't guess a URL, we still return no evidence rather than hallucinating.
            return []

        # ------------------------------------------------------------------
        # 2) Crawl a small set of pages (home + careers)
        # ------------------------------------------------------------------
        async with httpx.AsyncClient(headers=BROWSER_HEADERS, timeout=20.0, follow_redirects=True) as client:
            crawled_pages: Dict[str, str] = {}

            async def fetch_page(path: str) -> None:
                url = urljoin(base_url, path)
                try:
                    r = await client.get(url)
                    if r.status_code == 200 and "text/html" in r.headers.get("Content-Type", ""):
                        crawled_pages[url] = r.text
                        logger.info("WebProvider: fetched %s", url)
                except Exception as e:
                    logger.warning("WebProvider: error fetching %s (%r)", url, e)

            # Seed a small frontier: base, /careers, /jobs
            tasks = [
                fetch_page("/"),
                fetch_page("/careers"),
                fetch_page("/jobs"),
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

        # ------------------------------------------------------------------
        # 3) Extract raw text and discover GitHub link
        # ------------------------------------------------------------------
        all_text_chunks: List[str] = []
        github_urls: List[str] = []

        for url, html in crawled_pages.items():
            soup = BeautifulSoup(html, "html.parser")
            # text
            text = soup.get_text(separator="\n", strip=True)
            all_text_chunks.append(text)

            # discover GitHub links
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "github.com" in href:
                    github_urls.append(href)

        combined_text = "\n".join(all_text_chunks).lower()

        # ------------------------------------------------------------------
        # 4) Optionally inspect GitHub profile (very light)
        # ------------------------------------------------------------------
        github_langs: List[str] = []
        if github_urls:
            github_root = self._normalize_github_url(github_urls[0])
            if github_root:
                github_langs = await self._fetch_github_languages(github_root)

        # ------------------------------------------------------------------
        # 5) Detect technologies from text + GitHub using LLM
        # ------------------------------------------------------------------
        system_prompt = """You are an expert Technology Intelligence Analyst.
Extract the technology stack of a company based on the provided text crawled from their website.
Return a JSON object with two main keys: 'technology_profile' and 'technology_intelligence'.
The 'technology_profile' should contain arrays of strings for: languages, ai_frameworks, cloud, containers, developer_platforms, products, innovation_focus.
The 'technology_intelligence' should contain arrays of strings for: core_platforms, programming_languages, frontend_frameworks, backend_frameworks, ai_ml_frameworks, cloud_providers, databases, data_engineering, containerization, orchestration, ci_cd, monitoring, security, cdn, api_technologies, mobile_technologies, web_servers.
If a category has no matches, return an empty array. Do not invent information."""
        
        # We truncate `combined_text` to avoid exceeding token limits.
        max_chars = 25000
        truncated_text = combined_text[:max_chars]
        user_prompt = f"Company text snippet:\n{truncated_text}\n\nGitHub languages:\n{github_langs}\n\nExtract the technology stack in JSON format."
        
        technology_profile = {}
        technology_intelligence = {}
        
        try:
            llm_result = await ProviderRouter.generate_json(
                agent_name="technology_agent",
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            technology_profile = llm_result.get("technology_profile", {})
            technology_intelligence = llm_result.get("technology_intelligence", {})
        except Exception as e:
            logger.warning(f"WebProvider LLM extraction failed: {e}. Falling back to empty profile.")
            
        # Ensure default shapes exist
        default_profile = {
            "languages": [], "ai_frameworks": [], "cloud": [], 
            "containers": [], "developer_platforms": [], "products": [], "innovation_focus": []
        }
        default_intelligence = {
            "core_platforms": [], "programming_languages": [], "frontend_frameworks": [], 
            "backend_frameworks": [], "ai_ml_frameworks": [], "cloud_providers": [], 
            "databases": [], "data_engineering": [], "containerization": [], "orchestration": [], 
            "ci_cd": [], "monitoring": [], "security": [], "cdn": [], "api_technologies": [], 
            "mobile_technologies": [], "web_servers": []
        }
        
        # Merge fetched with defaults
        for k in default_profile:
            if k not in technology_profile or not isinstance(technology_profile[k], list):
                technology_profile[k] = []
                
        for k in default_intelligence:
            if k not in technology_intelligence or not isinstance(technology_intelligence[k], list):
                technology_intelligence[k] = []

        # ------------------------------------------------------------------
        # 7) Emit ResearchEvidence
        # ------------------------------------------------------------------
        tech_profile_id = CitationManager.generate_id(
            "technology_profile",
            company_key,
            "technology_profile",
            "current",
        )
        evidence_list.append(
            ResearchEvidence(
                id=tech_profile_id,
                entity=company_key,
                attribute="technology_profile",
                value=technology_profile,
                source="technology_profile",
                source_type="mcp",
                confidence=0.7,  # heuristic, because detection is keyword-based
            )
        )

        tech_intel_id = CitationManager.generate_id(
            "technology_intelligence",
            company_key,
            "technology_intelligence",
            "current",
        )
        evidence_list.append(
            ResearchEvidence(
                id=tech_intel_id,
                entity=company_key,
                attribute="technology_intelligence",
                value=technology_intelligence,
                source="technology_profile",
                source_type="mcp",
                confidence=0.7,
            )
        )

        _write_json(
            f"web_evidence_{company_key.replace(' ', '_')[:40]}.json",
            [e.model_dump(mode="json") for e in evidence_list],
        )

        return evidence_list

    # ----------------------------------------------------------------------
    # URL guessing / normalization
    # ----------------------------------------------------------------------

    def _guess_company_url(self, company: str) -> Optional[str]:
        """
        Very naive URL guesser: in a real system this would be replaced by
        company metadata or a search/API call.

        For now, just try https://{company}.com if it looks like a single token.
        """
        token = company.lower().replace(" ", "")
        if not token:
            return None
        return f"https://{token}.com"

    def _normalize_github_url(self, url: str) -> Optional[str]:
        """
        Normalize to https://github.com/{org_or_user}
        """
        parsed = urlparse(url)
        if "github.com" not in parsed.netloc:
            return None
        parts = [p for p in parsed.path.split("/") if p]
        if not parts:
            return None
        return f"https://github.com/{parts[0]}"

    # ----------------------------------------------------------------------
    # GitHub inspection (very light)
    # ----------------------------------------------------------------------

    async def _fetch_github_languages(self, github_root: str) -> List[str]:
        """
        Fetch a list of languages from the GitHub profile page by scraping the
        'Most used languages' section on the user/org homepage.

        Note: this is heuristic and HTML-structure-dependent.
        """
        langs: List[str] = []
        try:
            async with httpx.AsyncClient(headers=BROWSER_HEADERS, timeout=60.0, follow_redirects=True) as client:
                r = await client.get(github_root)
                if r.status_code != 200:
                    return []
                soup = BeautifulSoup(r.text, "html.parser")
                text = soup.get_text(separator="\n", strip=True).lower()
                # Cheap detection based on common languages
                candidates = [
                    "python",
                    "java",
                    "javascript",
                    "typescript",
                    "go",
                    "rust",
                    "c++",
                    "c#",
                    "php",
                    "ruby",
                ]
                for lang in candidates:
                    if lang in text:
                        langs.append(lang.capitalize() if lang != "c++" else "C++")
        except Exception:
            logger.exception("WebProvider: error fetching GitHub languages for %s", github_root)
        return list(set(langs))


