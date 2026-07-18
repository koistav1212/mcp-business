import asyncio
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urljoin, urlparse

from crawl4ai import AsyncWebCrawler

from services.research.base import BaseProvider
from services.knowledge.evidence import ResearchEvidence
from services.knowledge.citation_manager import CitationManager
from services.research.providers.shared_utils import logger, _write_json, _emit


class CompetitorProvider(BaseProvider):
    """
    Dedicated Competitor Intelligence provider.

    Fills every field the section_generation stage expects for
    'Competitor Intelligence', producing SIX distinct, independently
    evidenced analyses instead of one empty stub:

      1. competitive_matrix   - identified peers + attributes
      2. positioning          - market position summary
      3. swot                 - strengths/weaknesses/opportunities/threats
      4. pricing_comparison   - company vs peer pricing snippets
      5. feature_comparison   - company vs peer product/feature snippets
      6. white_space          - gaps implied by peer coverage the company lacks
      7. moat                 - competitive-advantage / threat narrative source

    NOTE: this provider must be registered in planner_agent.PROVIDER_MAP as
    "competitors": "competitor_provider" for the planner to ever schedule it.
    That one-line registration is outside the scope of this file per
    instructions, but the Competitor Intelligence section stays empty
    without it.
    """

    MAX_SNIPPET_CHARS = 1200
    MAX_COMPETITORS = 6

    # Very common corporate-suffix / stopword tokens filtered out of
    # heuristic name extraction so we don't emit junk like "The Company".
    _STOPWORDS = {
        "the", "and", "for", "with", "from", "this", "that", "your", "their",
        "about", "company", "companies", "inc", "llc", "ltd", "vs", "top",
        "best", "review", "reviews", "alternative", "alternatives", "guide",
        "news", "search", "results", "home", "page",
    }

    async def fetch(self, target: Any) -> List[ResearchEvidence]:
        company_name, industry_hint = self._resolve_company(target)
        if not company_name:
            logger.warning("CompetitorProvider: could not resolve a company name from target")
            return []

        company_key = company_name.strip().lower()
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        evidence_list: List[ResearchEvidence] = []

        async with AsyncWebCrawler() as crawler:
            competitors = await self._identify_competitors(crawler, company_name, industry_hint)

            # Run the remaining five analyses concurrently once we know the peer set.
            swot_task = self._analyze_swot(crawler, company_name)
            pricing_task = self._analyze_pricing(crawler, company_name, competitors)
            features_task = self._analyze_features(crawler, company_name, competitors)
            moat_task = self._analyze_moat_and_threats(crawler, company_name)

            swot, pricing, features, moat_threats = await asyncio.gather(
                swot_task, pricing_task, features_task, moat_task
            )

        positioning = self._build_positioning(company_name, competitors)
        competitive_matrix = self._build_matrix(company_name, competitors)
        white_space = self._build_white_space(company_name, competitors, features)

        analyses = [
            ("competitive_matrix", competitive_matrix, 0.75),
            ("positioning", positioning, 0.7),
            ("swot", swot, 0.7),
            ("pricing_comparison", pricing, 0.65),
            ("feature_comparison", features, 0.65),
            ("white_space", white_space, 0.6),
            ("threats", moat_threats.get("threats", []), 0.65),
            ("moat", moat_threats.get("moat", ""), 0.65),
        ]

        for attribute, value, confidence in analyses:
            if not value:
                continue
            evidence_id = CitationManager.generate_id(attribute, company_key, "competitor_provider", now_str)
            evidence_list.append(
                ResearchEvidence(
                    id=evidence_id,
                    entity=company_key,
                    attribute=attribute,
                    value=value,
                    source="competitor_provider",
                    source_type="mcp",
                    confidence=confidence,
                    metadata={"competitors_considered": [c["name"] for c in competitors]},
                )
            )

        _write_json(
            f"competitor_evidence_{company_key.replace(' ', '_')[:40]}.json",
            [e.model_dump(mode="json") for e in evidence_list],
        )
        logger.info(
            f"CompetitorProvider: {len(evidence_list)} evidence items "
            f"({len(competitors)} peers identified) for {company_name}"
        )
        return evidence_list

    # ------------------------------------------------------------------ #
    # 1. Peer identification
    # ------------------------------------------------------------------ #
    async def _identify_competitors(
        self, crawler: AsyncWebCrawler, company_name: str, industry_hint: Optional[str]
    ) -> List[Dict[str, Any]]:
        query = f"{company_name} top competitors alternatives"
        url = f"https://search.yahoo.com/search?p={quote(query)}"
        markdown = await self._safe_crawl(crawler, url)
        candidates = self._extract_candidate_names(markdown, exclude=company_name)

        competitors = []
        for name in candidates[: self.MAX_COMPETITORS]:
            competitors.append(
                {
                    "name": name,
                    "segment": industry_hint or "unspecified",
                    "source_url": url,
                }
            )
        return competitors

    def _extract_candidate_names(self, markdown: str, exclude: str) -> List[str]:
        if not markdown:
            return []
        # Heuristic: capitalized 1-3 word sequences that look like brand names.
        pattern = re.compile(r"\b([A-Z][a-zA-Z0-9&\.]+(?:\s+[A-Z][a-zA-Z0-9&\.]+){0,2})\b")
        seen = set()
        results = []
        exclude_norm = exclude.strip().lower()
        for match in pattern.findall(markdown):
            norm = match.strip().lower()
            if not norm or norm == exclude_norm:
                continue
            if norm in self._STOPWORDS or any(tok in self._STOPWORDS for tok in norm.split()):
                continue
            if len(norm) < 3 or len(norm) > 40:
                continue
            if norm in seen:
                continue
            seen.add(norm)
            results.append(match.strip())
        return results

    # ------------------------------------------------------------------ #
    # 2. Positioning
    # ------------------------------------------------------------------ #
    def _build_positioning(self, company_name: str, competitors: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not competitors:
            return {}
        return {
            "market_position": "contested" if len(competitors) >= 3 else "niche",
            "peer_count_identified": len(competitors),
            "summary": (
                f"{company_name} operates alongside {len(competitors)} identified peers "
                f"({', '.join(c['name'] for c in competitors[:4])}"
                f"{'...' if len(competitors) > 4 else ''})."
            ),
        }

    # ------------------------------------------------------------------ #
    # 3. Competitive matrix
    # ------------------------------------------------------------------ #
    def _build_matrix(self, company_name: str, competitors: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not competitors:
            return {}
        return {
            "list": [company_name] + [c["name"] for c in competitors],
            "attributes": {
                c["name"]: {"segment": c["segment"], "source_url": c["source_url"]}
                for c in competitors
            },
        }

    # ------------------------------------------------------------------ #
    # 4. SWOT
    # ------------------------------------------------------------------ #
    async def _analyze_swot(self, crawler: AsyncWebCrawler, company_name: str) -> Dict[str, Any]:
        strengths_md = await self._safe_crawl(
            crawler, f"https://search.yahoo.com/search?p={quote(company_name + ' strengths weaknesses analysis')}"
        )
        opportunities_md = await self._safe_crawl(
            crawler, f"https://search.yahoo.com/search?p={quote(company_name + ' opportunities threats market')}"
        )
        if not strengths_md and not opportunities_md:
            return {}
        return {
            "strengths": self._extract_sentences(strengths_md, "strength", limit=3),
            "weaknesses": self._extract_sentences(strengths_md, "weak", limit=3),
            "opportunities": self._extract_sentences(opportunities_md, "opportunit", limit=3),
            "threats": self._extract_sentences(opportunities_md, "threat", limit=3),
        }

    def _extract_sentences(self, markdown: str, keyword: str, limit: int) -> List[str]:
        if not markdown:
            return []
        sentences = re.split(r"(?<=[.!?])\s+", markdown)
        matches = [
            self._clean_text(s, limit=280) for s in sentences
            if keyword in s.lower() and 20 < len(s) < 280
        ]
        return matches[:limit]

    # ------------------------------------------------------------------ #
    # 5. Pricing comparison
    # ------------------------------------------------------------------ #
    async def _analyze_pricing(
        self, crawler: AsyncWebCrawler, company_name: str, competitors: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        company_pricing = await self._crawl_guessed_path(crawler, company_name, "/pricing")
        competitor_pricing = {}
        for c in competitors:
            snippet = await self._crawl_guessed_path(crawler, c["name"], "/pricing")
            if snippet:
                competitor_pricing[c["name"]] = snippet
        if not company_pricing and not competitor_pricing:
            return {}
        return {
            "company_pricing": company_pricing,
            "competitor_pricing": competitor_pricing,
        }

    # ------------------------------------------------------------------ #
    # 6. Feature comparison
    # ------------------------------------------------------------------ #
    async def _analyze_features(
        self, crawler: AsyncWebCrawler, company_name: str, competitors: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        company_features = await self._crawl_guessed_path(crawler, company_name, "/products")
        competitor_features = {}
        for c in competitors:
            snippet = await self._crawl_guessed_path(crawler, c["name"], "/products")
            if snippet:
                competitor_features[c["name"]] = snippet
        if not company_features and not competitor_features:
            return {}
        return {
            "company_features": company_features,
            "competitor_features": competitor_features,
        }

    # ------------------------------------------------------------------ #
    # 7. White space (gap analysis) + moat/threats
    # ------------------------------------------------------------------ #
    def _build_white_space(
        self, company_name: str, competitors: List[Dict[str, Any]], features: Dict[str, Any]
    ) -> List[str]:
        competitor_features = (features or {}).get("competitor_features", {})
        if not competitor_features:
            return []
        gaps = []
        for peer_name, snippet in competitor_features.items():
            if snippet and len(snippet) > 40:
                gaps.append(
                    f"Peer '{peer_name}' publicly emphasizes product themes not confirmed "
                    f"in {company_name}'s own crawled product pages -- verify before citing as a true gap."
                )
        return gaps[:5]

    async def _analyze_moat_and_threats(self, crawler: AsyncWebCrawler, company_name: str) -> Dict[str, Any]:
        moat_md = await self._safe_crawl(
            crawler, f"https://search.yahoo.com/search?p={quote(company_name + ' competitive advantage moat')}"
        )
        threat_md = await self._safe_crawl(
            crawler, f"https://search.yahoo.com/search?p={quote(company_name + ' competitive threats disruption risk')}"
        )
        if not moat_md and not threat_md:
            return {}
        return {
            "moat": " ".join(self._extract_sentences(moat_md, "advantage", limit=2))
            or " ".join(self._extract_sentences(moat_md, "moat", limit=2)),
            "threats": self._extract_sentences(threat_md, "threat", limit=3)
            or self._extract_sentences(threat_md, "risk", limit=3),
        }

    # ------------------------------------------------------------------ #
    # Shared crawl / text helpers
    # ------------------------------------------------------------------ #
    async def _safe_crawl(self, crawler: AsyncWebCrawler, url: str) -> str:
        try:
            result = await crawler.arun(url=url)
            markdown = getattr(result, "markdown", "") if result else ""
            return self._clean_text(markdown, limit=self.MAX_SNIPPET_CHARS * 3)
        except Exception as exc:
            logger.warning(f"CompetitorProvider: crawl failed for {url} ({exc})")
            return ""

    async def _crawl_guessed_path(self, crawler: AsyncWebCrawler, company: str, path: str) -> Optional[str]:
        base_url = self._guess_company_url(company)
        if not base_url:
            return None
        url = urljoin(base_url, path)
        markdown = await self._safe_crawl(crawler, url)
        if not markdown:
            return None
        return markdown[: self.MAX_SNIPPET_CHARS]

    def _guess_company_url(self, company: str) -> Optional[str]:
        token = re.sub(r"[^a-z0-9]", "", company.lower())
        if not token:
            return None
        return f"https://{token}.com/"

    def _clean_text(self, value: str, limit: int) -> str:
        if not value:
            return ""
        text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", value)
        text = re.sub(r"\[[^\]]+\]\([^)]+\)", " ", text)
        text = re.sub(r"`{1,3}", " ", text)
        text = re.sub(r"[#>*_\-]{2,}", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > limit:
            text = text[: limit - 3].rstrip() + "..."
        return text

    def _resolve_company(self, target: Any) -> (Optional[str], Optional[str]):
        if isinstance(target, str):
            return target.strip(), None

        company_name = self._extract_identifier(target, preferred_key="company")
        industry = None
        if isinstance(target, dict):
            industry = target.get("industry")
            entity = target.get("entity", {}) if isinstance(target.get("entity"), dict) else {}
            industry = industry or entity.get("industry")
            company_name = company_name or target.get("canonical_name") or entity.get("name")
        return company_name, industry
