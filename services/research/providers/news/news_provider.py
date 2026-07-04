import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Any

from services.research.base import BaseProvider
from services.knowledge.evidence import ResearchEvidence
from services.knowledge.citation_manager import CitationManager

from .rss_sources import GoogleNewsRSS, YahooFinanceRSS, ReutersRSS, FinancialTimesRSS
from .newsapi_client import NewsAPIClient
from .gnews_client import GNewsClient
from .article_fetcher import ArticleFetcher
from .article_parser import ArticleParser
from .classifier import BusinessSignalClassifier
from .entity_extractor import EntityExtractor
from .semantic_ranker import SemanticRanker
from .duplicate_detector import DuplicateDetector
from .event_clusterer import EventClusterer
from .timeline_builder import TimelineBuilder
from .source_ranker import SourceRanker
from services.artifacts.artifact_writer import ArtifactWriter
from .models import NewsEvidence

logger = logging.getLogger("uvicorn.error")

class NewsProvider(BaseProvider):
    """
    Enterprise News Intelligence Pipeline.
    Collects, extracts, embeds, deduplicates, and ranks news articles.
    """
    
    async def fetch(self, target: Any) -> List[ResearchEvidence]:
        company = self._extract_identifier(target)
        if not company:
            return []
            
        company_clean = company.lower().strip()
        ticker = getattr(target, "ticker", None) if hasattr(target, "ticker") else None
        
        # 1. Initialize Collectors
        collectors = [
            GoogleNewsRSS().fetch(company_clean, ticker),
            YahooFinanceRSS().fetch(company_clean, ticker),
            ReutersRSS().fetch(company_clean, ticker),
            FinancialTimesRSS().fetch(company_clean, ticker),
            NewsAPIClient().fetch(company_clean),
            GNewsClient().fetch(company_clean)
        ]
        
        # 2. Parallel Fetch
        results = await asyncio.gather(*collectors, return_exceptions=True)
        
        raw_articles = []
        for res in results:
            if isinstance(res, list):
                raw_articles.extend(res)
                
        if not raw_articles:
            return []
            
        # 3. Source Ranking
        ranked_articles = SourceRanker().rank(raw_articles)
        
        # 4. Article Download
        fetcher = ArticleFetcher()
        html_articles = await fetcher.fetch_all(ranked_articles)
        
        # 5. Parsing & Extraction
        parser = ArticleParser()
        parsed_articles = parser.parse_all(html_articles)
        
        # Merge parsed content back into ranked_articles by URL or id
        articles_enriched = []
        parsed_by_url = {p.get("url"): p for p in parsed_articles if p.get("url")}
        for base in ranked_articles:
            url = base.get("url")
            parsed = parsed_by_url.get(url, {})
            merged = {**base, **parsed}  # parsed fields (full_text, entities) override base if present
            articles_enriched.append(merged)

        # If parsing totally fails, we still continue with base articles
        if not articles_enriched:
            articles_enriched = ranked_articles
            
        # 6. Classification & Entity Extraction
        classifier = BusinessSignalClassifier()
        classified = classifier.process_all(articles_enriched)
        
        extractor = EntityExtractor()
        extracted = extractor.process_all(classified)
        
        # 7. Semantic Ranking (Embeddings)
        ranker = SemanticRanker()
        embedded = ranker.process_all(extracted)
        
        # 8. Deduplication
        deduplicator = DuplicateDetector(threshold=0.92)
        deduped = deduplicator.deduplicate(embedded)
        
        # 9. Event Clustering
        clusterer = EventClusterer(threshold=0.75)
        clustered = clusterer.cluster(deduped)
        
        # 10. Timeline & Final Ranking
        timeline = TimelineBuilder().build(clustered)
        SIGNAL_WEIGHTS = {
            "earnings": 1.0,
            "guidance": 0.9,
            "m_and_a": 0.9,
            "regulation": 0.85,
            "product_launch": 0.8,
            "macro": 0.7,
            "general": 0.6,
        }

        for art in timeline:
            base_source = art.get("source_score", 0.5)
            base_sem = art.get("semantic_score", 0.5)
            signal_type = art.get("signal_type", "general")
            
            if isinstance(signal_type, list):
                signal_w = max([SIGNAL_WEIGHTS.get(st, 0.6) for st in signal_type]) if signal_type else 0.6
            else:
                signal_w = SIGNAL_WEIGHTS.get(signal_type, 0.6)

            # importance = base average * signal weight
            art["importance"] = ((base_source + base_sem) / 2.0) * signal_w

        final_ranked = sorted(timeline, key=lambda x: x.get("importance", 0.0), reverse=True)
        top_articles = final_ranked[:100]  # top 100 instead of 25
        
        # Convert to ResearchEvidence
        evidence_list = []
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        for idx, art in enumerate(top_articles):
            news_model = NewsEvidence(**art)
            
            # Compress for the LLM prompt to save tokens (500-700 token budget)
            compressed_value = {
                "headline": news_model.headline,
                "summary": news_model.summary,
                "publisher": news_model.publisher,
                "published_at": news_model.published_at.isoformat() if news_model.published_at else None,
                "signal_type": news_model.signal_type,
                "event_cluster": news_model.event_cluster
            }
            
            evidence_list.append(ResearchEvidence(
                id=CitationManager.generate_id("news_intelligence", company_clean, f"news_event_{idx}", now_str),
                entity=company_clean,
                attribute="news_intelligence",
                value=compressed_value,
                source="news_intelligence_pipeline",
                source_type="mcp",
                source_url=news_model.url,
                confidence=news_model.confidence,
                freshness=now_str
            ))
            
        ArtifactWriter.write_json(f"provider_outputs/news_evidence_{company_clean.replace(' ', '_')[:40]}.json", [e.model_dump(mode='json') for e in evidence_list])
            
        return evidence_list
