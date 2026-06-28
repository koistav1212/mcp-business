# services/research/providers/social_intelligence_provider.py

import asyncio
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from services.research.base import BaseProvider
from services.knowledge.evidence import ResearchEvidence
from services.research.providers.shared_utils import (
    _get,
    _write_json,
    _emit,
    logger,
    BROWSER_HEADERS,
    JSON_HEADERS,
)


@dataclass
class SocialPost:
    """
    Normalized social/discussion post.

    source: "reddit" | "stocktwits" | "hackernews"
    """
    source: str
    title: str
    body: str
    url: str
    score: int
    comments: int
    created_at: Optional[datetime]
    subreddit: Optional[str] = None
    symbol: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class RedditProvider(BaseProvider):
    """
    Aggregated social & discussion intelligence for a company/ticker.

    Sources:
      - Reddit JSON Search
      - Reddit Subreddit Search (financial + tech)
      - StockTwits API
      - Hacker News Algolia API
    """

    _FINANCIAL_SUBS = [
        "stocks",
        "investing",
        "SecurityAnalysis",
        "wallstreetbets",
        "ValueInvesting",
        "StockMarket",
        "FinancialIndependence",
    ]

    _TECH_SUBS = [
        "technology",
        "programming",
        "MachineLearning",
        "artificial",
        "computerscience",
    ]

    # Very lightweight “NLP” vocab – keyword based
    _EXECUTIVE_PATTERNS = [
        r"\bceo\b",
        r"\bcto\b",
        r"\bcfo\b",
        r"\bcoo\b",
        r"\bchief\s+executive\b",
        r"\bchief\s+technology\b",
        r"\bchief\s+financial\b",
    ]

    _DEV_PATTERNS = [
        r"\bapi\b",
        r"\bsdk\b",
        r"\bopen\s*source\b",
        r"\bbug\b",
        r"\bcrash(es)?\b",
        r"\bsegfault\b",
        r"\bcompile\b",
        r"\bbuild\b",
        r"\bdeployment\b",
        r"\bkubernetes\b",
        r"\bmicroservice(s)?\b",
        r"\bdev(ops)?\b",
        r"\bbenchmark\b",
    ]

    _HIRING_PATTERNS = [
        r"\bhiring\b",
        r"\bjob(s)?\b",
        r"\binterview\b",
        r"\boffer\b",
        r"\brecruit(er|ing)\b",
        r"\bcareer\b",
        r"\bposition\b",
    ]

    _PAIN_PATTERNS = [
        r"\bissue(s)?\b",
        r"\bproblem(s)?\b",
        r"\bpain\b",
        r"\bbug(s)?\b",
        r"\bcrash(es)?\b",
        r"\bfailure(s)?\b",
        r"\bdoes\s+not\s+work\b",
        r"\bnot\s+working\b",
        r"\bterrible\b",
        r"\bawful\b",
        r"\bworst\b",
        r"\bfrustrating\b",
        r"\binstability\b",
        r"\binstall(ation)?\b",
    ]

    _PRODUCT_PATTERNS = [
        r"\bproduct\b",
        r"\bfeature\b",
        r"\brelease\b",
        r"\blaunch\b",
        r"\bupdate\b",
        r"\bversion\s+\d+",
    ]

    _POSITIVE_KW = {
        "bullish",
        "buy",
        "long",
        "growth",
        "beat",
        "surge",
        "rally",
        "undervalued",
        "strong",
        "solid",
        "impressive",
        "opportunity",
        "outperform",
        "great",
        "awesome",
        "love",
        "amazing",
        "upside",
        "positive",
    }

    _NEGATIVE_KW = {
        "bearish",
        "sell",
        "short",
        "overvalued",
        "miss",
        "decline",
        "crash",
        "fraud",
        "lawsuit",
        "layoffs",
        "disappointing",
        "weak",
        "avoid",
        "downside",
        "terrible",
        "awful",
        "hate",
        "concern",
        "negative",
    }

    async def fetch(self, target: Any) -> List[ResearchEvidence]:
        """
        Entry point: fetch cross-source social intelligence for a given company/ticker.

        Returns:
            List[ResearchEvidence]: multiple evidence objects for different attributes.
        """
        company = self._extract_identifier(target)
        if not company:
            return []

        company_clean = company.strip()
        ticker = getattr(target, "ticker", None) if hasattr(target, "ticker") else None
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        evidence_list: List[ResearchEvidence] = []

        # Collect posts concurrently
        async with httpx.AsyncClient(
            headers=BROWSER_HEADERS,
            follow_redirects=True,
            timeout=20.0,
        ) as client:
            tasks = [
                self._fetch_reddit_global_search(client, company_clean),
                self._fetch_reddit_subreddits(client, company_clean),
                self._fetch_stocktwits_messages(client, ticker),
                self._fetch_hn_stories(client, company_clean),
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        reddit_global: List[SocialPost] = results[0] if isinstance(results[0], list) else []
        reddit_subs: List[SocialPost] = results[1] if isinstance(results[1], list) else []
        stocktwits_posts: List[SocialPost] = results[2] if isinstance(results[2], list) else []
        hn_posts: List[SocialPost] = results[3] if isinstance(results[3], list) else []

        all_posts: List[SocialPost] = reddit_global + reddit_subs + stocktwits_posts + hn_posts

        # Build social intelligence JSON payload
        payload = self._build_social_intelligence_payload(
            company_clean,
            ticker,
            all_posts,
        )

        # Persist artifact (for debugging / offline analysis)
        safe_prefix = company_clean.replace(" ", "_")[:40]
        artifact_name = f"social_intel_{safe_prefix}.json"
        _write_json(artifact_name, payload)

        # Emit ResearchEvidence objects from payload
        evidence_list.extend(self._emit_from_payload(company_clean, ticker, payload, now_str))
        
        _write_json(f"reddit_evidence_{safe_prefix}.json", [e.model_dump(mode='json') for e in evidence_list])

        logger.info(
            "RedditProvider: %d posts for '%s' (ticker=%s)",
            len(all_posts),
            company_clean,
            ticker,
        )

        return evidence_list

    # -------------------------------------------------------------------------
    # FETCHING LAYERS
    # -------------------------------------------------------------------------

    async def _fetch_reddit_global_search(
        self,
        client: httpx.AsyncClient,
        company: str,
    ) -> List[SocialPost]:
        """
        Reddit search across all of Reddit for the company name.
        """
        query = quote_plus(company)
        url = (
            f"https://www.reddit.com/search.json?"
            f"q={query}&sort=new&limit=50&t=month"
        )
        r = await _get(
            client,
            url,
            headers={**BROWSER_HEADERS, "Accept": "application/json"},
        )
        if not r:
            return []

        posts: List[SocialPost] = []
        try:
            data = r.json().get("data", {})
            for child in data.get("children", []):
                d = child.get("data", {})
                title = d.get("title", "") or ""
                body = self._first_lines(
                    d.get("selftext", "") or "",
                    max_lines=6,
                    max_chars=1200,
                )
                score = int(d.get("score", 0)) if d.get("score") is not None else 0
                comments = int(d.get("num_comments", 0)) if d.get("num_comments") is not None else 0
                url_post = f"https://reddit.com{d.get('permalink', '')}"
                created_utc = d.get("created_utc")
                created_dt = (
                    datetime.fromtimestamp(created_utc, tz=timezone.utc)
                    if isinstance(created_utc, (int, float))
                    else None
                )
                subreddit = d.get("subreddit", "")

                posts.append(
                    SocialPost(
                        source="reddit",
                        title=title,
                        body=body,
                        url=url_post,
                        score=score,
                        comments=comments,
                        created_at=created_dt,
                        subreddit=subreddit,
                        symbol=None,
                        extra={"kind": "global"},
                    )
                )
        except Exception:
            logger.exception("RedditProvider: error parsing reddit global search")
        return posts

    async def _fetch_reddit_subreddits(
        self,
        client: httpx.AsyncClient,
        company: str,
    ) -> List[SocialPost]:
        """
        Reddit searches in curated financial + tech subreddits.
        """
        posts: List[SocialPost] = []
        query = quote_plus(company)
        subs = list(dict.fromkeys(self._FINANCIAL_SUBS + self._TECH_SUBS))

        for sub in subs:
            url = (
                f"https://www.reddit.com/r/{sub}/search.json?"
                f"q={query}&restrict_sr=1&sort=new&limit=30&t=month"
            )
            r = await _get(
                client,
                url,
                headers={**BROWSER_HEADERS, "Accept": "application/json"},
            )
            if not r:
                continue

            try:
                data = r.json().get("data", {})
                for child in data.get("children", []):
                    d = child.get("data", {})
                    title = d.get("title", "") or ""
                    body = self._first_lines(
                        d.get("selftext", "") or "",
                        max_lines=6,
                        max_chars=1200,
                    )
                    score = int(d.get("score", 0)) if d.get("score") is not None else 0
                    comments = int(d.get("num_comments", 0)) if d.get("num_comments") is not None else 0
                    url_post = f"https://reddit.com{d.get('permalink', '')}"
                    created_utc = d.get("created_utc")
                    created_dt = (
                        datetime.fromtimestamp(created_utc, tz=timezone.utc)
                        if isinstance(created_utc, (int, float))
                        else None
                    )

                    posts.append(
                        SocialPost(
                            source="reddit",
                            title=title,
                            body=body,
                            url=url_post,
                            score=score,
                            comments=comments,
                            created_at=created_dt,
                            subreddit=sub,
                            symbol=None,
                            extra={"kind": "subreddit"},
                        )
                    )
            except Exception:
                logger.exception(
                    "RedditProvider: error parsing subreddit %s search",
                    sub,
                )

        return posts

    async def _fetch_stocktwits_messages(
        self,
        client: httpx.AsyncClient,
        ticker: Optional[str],
    ) -> List[SocialPost]:
        """
        StockTwits stream for a given ticker – normalized into SocialPost objects.
        """
        if not ticker or "MOCK" in ticker.upper():
            return []

        url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
        r = await _get(client, url, headers=JSON_HEADERS)
        if not r:
            return []

        posts: List[SocialPost] = []
        try:
            data = r.json()
            messages = data.get("messages", [])
            for msg in messages:
                body_raw = msg.get("body", "") or ""
                body = self._first_lines(body_raw, max_lines=6, max_chars=1200)
                title = (msg.get("entities", {}).get("symbol", {}) or {}).get("title") or ticker
                url_msg = msg.get("url", "") or ""
                created_at_str = msg.get("created_at")
                created_dt: Optional[datetime] = None
                if created_at_str:
                    try:
                        created_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    except Exception:
                        created_dt = None
                likes = int(msg.get("likes", {}).get("total", 0))
                reshares = int(msg.get("reshares", {}).get("total", 0))
                sentiment = msg.get("entities", {}).get("sentiment", {}).get("basic")
                score = likes + reshares
                comments = 0  # StockTwits does not expose threaded comments the same way

                posts.append(
                    SocialPost(
                        source="stocktwits",
                        title=title,
                        body=body,
                        url=url_msg,
                        score=score,
                        comments=comments,
                        created_at=created_dt,
                        subreddit=None,
                        symbol=ticker,
                        extra={"sentiment": sentiment, "likes": likes, "reshares": reshares},
                    )
                )
        except Exception:
            logger.exception("RedditProvider: error parsing StockTwits response")

        return posts

    async def _fetch_hn_stories(
        self,
        client: httpx.AsyncClient,
        company: str,
    ) -> List[SocialPost]:
        """
        HackerNews Algolia search API for company name.
        """
        query = quote_plus(company)
        url = (
            "https://hn.algolia.com/api/v1/search?"
            f"query={query}&tags=story&hitsPerPage=40"
        )
        r = await _get(client, url, headers={**JSON_HEADERS, "Accept": "application/json"})
        if not r:
            return []

        posts: List[SocialPost] = []
        try:
            data = r.json()
            for hit in data.get("hits", []):
                title = hit.get("title", "") or ""
                story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                points = int(hit.get("points", 0) or 0)
                num_comments = int(hit.get("num_comments", 0) or 0)
                created_i = hit.get("created_at_i")
                created_dt = (
                    datetime.fromtimestamp(int(created_i), tz=timezone.utc)
                    if created_i is not None
                    else None
                )

                # HN stories usually do not have “body”; use title + URL as main content.
                body = self._first_lines(
                    f"{title}\n{story_url}",
                    max_lines=6,
                    max_chars=800,
                )

                posts.append(
                    SocialPost(
                        source="hackernews",
                        title=title,
                        body=body,
                        url=story_url,
                        score=points,
                        comments=num_comments,
                        created_at=created_dt,
                        subreddit=None,
                        symbol=None,
                        extra={"hn_id": hit.get("objectID")},
                    )
                )
        except Exception:
            logger.exception("RedditProvider: error parsing HN Algolia response")

        return posts

    # -------------------------------------------------------------------------
    # ANALYTICS / NLP LAYER
    # -------------------------------------------------------------------------

    def _build_social_intelligence_payload(
        self,
        company: str,
        ticker: Optional[str],
        posts: List[SocialPost],
    ) -> Dict[str, Any]:
        """
        Construct the rich JSON structure from normalized posts.
        """

        # Engagement stats per source
        engagement = self._compute_engagement(posts)

        # Sentiment distribution
        sentiment = self._compute_sentiment(posts)

        # Trending topics (based on words in titles)
        trending_topics = self._extract_trending_topics(company, posts)

        # Thematic buckets (raw posts)
        exec_posts = self._extract_executive_mentions(posts)
        product_posts = self._extract_product_mentions(posts)
        pain_posts = self._extract_customer_pain_points(posts)
        dev_posts = self._extract_developer_discussions(posts)
        hiring_posts = self._extract_hiring_discussions(posts)

        # Aggregated thematic views
        executive_mentions = self._aggregate_executives(exec_posts)
        customer_pain_points = self._aggregate_pain_points(pain_posts)
        developer_discussions = self._aggregate_developer_topics(dev_posts)

        # Timeline events
        timeline = self._build_timeline(posts)

        # Discussion URLs
        discussion_urls = self._collect_discussion_urls(posts)

        # Source credibility (simple fixed priors)
        source_credibility = {
            "reddit": 0.72,
            "stocktwits": 0.81,
            "hackernews": 0.94,
        }

        # Summary with activity levels
        total_discussions = len(posts)
        overall_score = self._compute_overall_market_score(sentiment, engagement)
        summary = {
            "market_sentiment": self._label_market_sentiment(sentiment),
            "overall_score": overall_score,
            "discussion_volume": total_discussions,
            "executive_activity": self._activity_level(len(exec_posts)),
            "developer_activity": self._activity_level(len(dev_posts)),
            "product_activity": self._activity_level(len(product_posts)),
        }

        return {
            "entity": company,
            "ticker": ticker,
            "summary": summary,
            "trending_topics": trending_topics,
            "executive_mentions": executive_mentions,
            "product_mentions": [self._post_to_dict(p) for p in product_posts],
            "customer_pain_points": customer_pain_points,
            "developer_discussions": developer_discussions,
            "hiring_discussions": [self._post_to_dict(p) for p in hiring_posts],
            "market_sentiment": {
                "bullish": sentiment["bullish"],
                "bearish": sentiment["bearish"],
                "neutral": sentiment["neutral"],
                "confidence": sentiment["confidence"],
            },
            "timeline": timeline,
            "engagement": engagement,
            "source_credibility": source_credibility,
            "discussion_urls": discussion_urls,
        }

    def _compute_engagement(self, posts: List[SocialPost]) -> Dict[str, Any]:
        reddit_posts = [p for p in posts if p.source == "reddit"]
        stock_posts = [p for p in posts if p.source == "stocktwits"]
        hn_posts = [p for p in posts if p.source == "hackernews"]

        engagement = {
            "reddit": {
                "posts": len(reddit_posts),
                "upvotes": sum(p.score for p in reddit_posts),
                "comments": sum(p.comments for p in reddit_posts),
            },
            "stocktwits": {
                "messages": len(stock_posts),
                "likes": sum((p.extra or {}).get("likes", 0) for p in stock_posts),
            },
            "hackernews": {
                "stories": len(hn_posts),
                "points": sum(p.score for p in hn_posts),
                "comments": sum(p.comments for p in hn_posts),
            },
        }
        return engagement

    def _compute_sentiment(self, posts: List[SocialPost]) -> Dict[str, Any]:
        bullish = 0
        bearish = 0

        for p in posts:
            text = f"{p.title}\n{p.body}".lower()

            # If we have explicit StockTwits sentiment, use it as a strong hint
            if p.source == "stocktwits":
                sentiment = (p.extra or {}).get("sentiment")
                if sentiment == "Bullish":
                    bullish += 2
                    continue
                if sentiment == "Bearish":
                    bearish += 2
                    continue

            if any(k in text for k in self._POSITIVE_KW):
                bullish += 1
            if any(k in text for k in self._NEGATIVE_KW):
                bearish += 1

        total = max(1, bullish + bearish)
        bull_pct = round(bullish / total * 100, 1)
        bear_pct = round(bearish / total * 100, 1)
        neutral_pct = max(0.0, 100.0 - bull_pct - bear_pct)

        # Simple confidence heuristic: more posts => higher confidence
        num_posts = len(posts)
        confidence = min(0.95, 0.4 + min(num_posts / 100.0, 0.5))

        return {
            "bullish": bull_pct,
            "bearish": bear_pct,
            "neutral": neutral_pct,
            "confidence": round(confidence, 2),
        }

    def _extract_trending_topics(self, company: str, posts: List[SocialPost]) -> List[Dict[str, Any]]:
        stop_words = {
            "this",
            "that",
            "with",
            "from",
            "they",
            "have",
            "will",
            "what",
            "just",
            "been",
            "more",
            "also",
            "than",
            "into",
            "some",
            "about",
            "there",
            "their",
            "https",
            "http",
            "www",
            company.lower(),
        }

        word_counts: Counter = Counter()
        for p in posts:
            words = re.findall(r"\b[A-Za-z]{4,}\b", p.title or "")
            for w in words:
                wl = w.lower()
                if wl not in stop_words:
                    word_counts[wl] += 1

        topics: List[Dict[str, Any]] = []
        for topic, cnt in word_counts.most_common(15):
            topics.append({
                "topic": topic,
                "mentions": cnt,
                # growth is placeholder; proper growth requires historic baseline
                "growth": "+0%",
                "sentiment": self._topic_sentiment(topic, posts),
            })
        return topics

    def _topic_sentiment(self, topic: str, posts: List[SocialPost]) -> Optional[str]:
        rel_posts = [p for p in posts if topic.lower() in (p.title or "").lower()]
        if not rel_posts:
            return None
        s = self._compute_sentiment(rel_posts)
        if s["bullish"] > s["bearish"] + 10:
            return "Positive"
        if s["bearish"] > s["bullish"] + 10:
            return "Negative"
        return "Mixed"

    def _extract_executive_mentions(self, posts: List[SocialPost]) -> List[SocialPost]:
        res: List[SocialPost] = []
        for p in posts:
            text = f"{p.title}\n{p.body}".lower()
            if any(re.search(pattern, text) for pattern in self._EXECUTIVE_PATTERNS):
                res.append(p)
        return res

    def _extract_product_mentions(self, posts: List[SocialPost]) -> List[SocialPost]:
        res: List[SocialPost] = []
        for p in posts:
            text = f"{p.title}\n{p.body}".lower()
            if any(re.search(pattern, text) for pattern in self._PRODUCT_PATTERNS):
                res.append(p)
        return res

    def _extract_customer_pain_points(self, posts: List[SocialPost]) -> List[SocialPost]:
        res: List[SocialPost] = []
        for p in posts:
            text = f"{p.title}\n{p.body}".lower()
            if any(re.search(pattern, text) for pattern in self._PAIN_PATTERNS):
                res.append(p)
        return res

    def _extract_developer_discussions(self, posts: List[SocialPost]) -> List[SocialPost]:
        res: List[SocialPost] = []
        for p in posts:
            text = f"{p.title}\n{p.body}".lower()
            if any(re.search(pattern, text) for pattern in self._DEV_PATTERNS):
                res.append(p)
        return res

    def _extract_hiring_discussions(self, posts: List[SocialPost]) -> List[SocialPost]:
        res: List[SocialPost] = []
        for p in posts:
            text = f"{p.title}\n{p.body}".lower()
            if any(re.search(pattern, text) for pattern in self._HIRING_PATTERNS):
                res.append(p)
        return res

    def _aggregate_executives(self, exec_posts: List[SocialPost]) -> List[Dict[str, Any]]:
        """
        Group executive-related posts by inferred name and summarize.
        """
        exec_groups: Dict[str, List[SocialPost]] = defaultdict(list)

        for p in exec_posts:
            # crude name detection: capitalized First Last in title
            m = re.search(r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b", p.title)
            name = m.group(1) if m else "Unknown executive"
            exec_groups[name].append(p)

        results: List[Dict[str, Any]] = []
        for name, group_posts in exec_groups.items():
            sentiment = self._compute_sentiment(group_posts)
            text_all = "\n".join(f"{p.title}\n{p.body}" for p in group_posts).lower()
            role = "executive"
            if "ceo" in text_all:
                role = "CEO"
            elif "cto" in text_all:
                role = "CTO"
            elif "cfo" in text_all:
                role = "CFO"

            top_posts = sorted(
                group_posts,
                key=lambda p: (p.score or 0) + (p.comments or 0),
                reverse=True,
            )[:5]

            results.append({
                "executive": name,
                "role": role,
                "mentions": len(group_posts),
                "overall_sentiment": self._label_market_sentiment(sentiment),
                "discussion_count": len(group_posts),
                "posts": [
                    {
                        "title": p.title,
                        "body": p.body,
                        "score": p.score,
                        "comments": p.comments,
                        "source": p.source,
                        "url": p.url,
                    }
                    for p in top_posts
                ],
            })

        return results

    def _aggregate_pain_points(self, pain_posts: List[SocialPost]) -> List[Dict[str, Any]]:
        """
        Group pain point posts into simple themes based on key phrases.
        """
        themes: Dict[str, int] = defaultdict(int)

        for p in pain_posts:
            text = f"{p.title}\n{p.body}".lower()
            if "install" in text or "installation" in text:
                themes["CUDA installation"] += 1
            if "driver" in text:
                themes["Driver instability"] += 1
            if not any(k in text for k in ["install", "installation", "driver"]):
                themes["General issues"] += 1

        results: List[Dict[str, Any]] = []
        for theme, freq in themes.items():
            severity = "Low"
            if freq > 30:
                severity = "High"
            elif freq > 15:
                severity = "Moderate"
            results.append({
                "theme": theme,
                "frequency": freq,
                "severity": severity,
            })

        return results

    def _aggregate_developer_topics(self, dev_posts: List[SocialPost]) -> List[Dict[str, Any]]:
        """
        Group developer posts into key topics like 'TensorRT optimization', 'vLLM benchmark', etc.
        """
        topics: Dict[str, int] = defaultdict(int)

        for p in dev_posts:
            text = f"{p.title}\n{p.body}".lower()
            if "tensorrt" in text and "optim" in text:
                topics["TensorRT optimization"] += 1
            if "vllm" in text and "benchmark" in text:
                topics["vLLM benchmark"] += 1
            if "cuda" in text and "kernel" in text:
                topics["CUDA kernel development"] += 1
            if not any(k in topics for k in ["TensorRT optimization", "vLLM benchmark", "CUDA kernel development"]):
                topics["General developer discussion"] += 1

        results: List[Dict[str, Any]] = []
        for topic, cnt in topics.items():
            results.append({
                "topic": topic,
                "mentions": cnt,
            })
        return results

    def _build_timeline(self, posts: List[SocialPost]) -> List[Dict[str, Any]]:
        """
        Simple timeline: group posts by date and aggregate key sources.
        """
        per_day: Dict[str, List[SocialPost]] = defaultdict(list)
        for p in posts:
            if not p.created_at:
                continue
            day = p.created_at.date().isoformat()
            per_day[day].append(p)

        events: List[Dict[str, Any]] = []
        for day, day_posts in per_day.items():
            source_set = sorted({p.source for p in day_posts})
            # Choose most engaged post for label
            best = max(day_posts, key=lambda x: (x.score or 0) + (x.comments or 0))
            title = best.title or "(no title)"

            events.append(
                {
                    "date": day,
                    "event": title,
                    "sources": [s.capitalize() for s in source_set],
                    "url": best.url,
                }
            )

        events.sort(key=lambda e: e["date"])
        return events[:40]

    def _collect_discussion_urls(self, posts: List[SocialPost]) -> List[str]:
        urls: List[str] = []
        seen: set = set()
        for p in posts:
            if p.url and p.url not in seen:
                seen.add(p.url)
                urls.append(p.url)
        return urls[:200]

    def _compute_overall_market_score(
        self,
        sentiment: Dict[str, Any],
        engagement: Dict[str, Any],
    ) -> float:
        """
        Very simple composite score mixing sentiment and engagement.
        """
        bull = sentiment["bullish"]
        bear = sentiment["bearish"]
        conf = sentiment["confidence"]

        eng_reddit = engagement["reddit"]["posts"] + engagement["reddit"]["comments"]
        eng_stock = engagement["stocktwits"]["messages"] + engagement["stocktwits"]["likes"]
        eng_hn = engagement["hackernews"]["stories"] + engagement["hackernews"]["comments"]
        eng_total = eng_reddit + eng_stock + eng_hn

        # Normalize engagement roughly into [0, 1]
        eng_norm = min(1.0, eng_total / 1000.0)

        score = (bull - bear) / 100.0 * conf + eng_norm * 0.4
        return round(max(-1.0, min(1.0, score)), 3)

    def _label_market_sentiment(self, sentiment: Dict[str, Any]) -> str:
        bull = sentiment["bullish"]
        bear = sentiment["bearish"]
        neutral = sentiment["neutral"]

        if bull > bear + 10:
            return "bullish"
        if bear > bull + 10:
            return "bearish"
        if neutral > 60:
            return "mixed / neutral"
        return "balanced"

    @staticmethod
    def _activity_level(count: int) -> str:
        if count > 200:
            return "Extremely High"
        if count > 100:
            return "Very High"
        if count > 50:
            return "High"
        if count > 20:
            return "Moderate"
        if count > 0:
            return "Low"
        return "None"

    # -------------------------------------------------------------------------
    # UTILITIES
    # -------------------------------------------------------------------------

    @staticmethod
    def _first_lines(text: str, max_lines: int = 6, max_chars: int = 1200) -> str:
        """
        Return the first N lines of text (up to max_chars) without compressing too aggressively.
        """
        if not text:
            return ""
        lines = text.splitlines()
        selected = lines[:max_lines]
        joined = "\n".join(selected)
        if len(joined) <= max_chars:
            return joined
        return joined[: max_chars - 3] + "..."

    @staticmethod
    def _post_to_dict(p: SocialPost) -> Dict[str, Any]:
        return {
            "title": p.title,
            "body": p.body,
            "url": p.url,
            "score": p.score,
            "comments": p.comments,
            "source": p.source,
            "subreddit": p.subreddit,
            "symbol": p.symbol,
        }

    def _emit_from_payload(
        self,
        company: str,
        ticker: Optional[str],
        payload: Dict[str, Any],
        now_str: str,
    ) -> List[ResearchEvidence]:
        """
        Convert the JSON payload into multiple ResearchEvidence objects.
        """
        evidence_list: List[ResearchEvidence] = []

        # Market sentiment
        ms = payload.get("market_sentiment", {})
        _emit(
            evidence_list,
            entity=company,
            attribute="social_market_sentiment",
            value=ms,
            source="social_intel",
            source_type="mcp",
            confidence=ms.get("confidence", 0.75),
            now_str=now_str,
        )

        # Summary
        _emit(
            evidence_list,
            entity=company,
            attribute="social_summary",
            value=payload.get("summary", {}),
            source="social_intel",
            source_type="mcp",
            confidence=0.8,
            now_str=now_str,
        )

        # Trending topics
        _emit(
            evidence_list,
            entity=company,
            attribute="social_trending_topics",
            value=payload.get("trending_topics", []),
            source="social_intel",
            source_type="mcp",
            confidence=0.7,
            now_str=now_str,
        )

        # Engagement
        _emit(
            evidence_list,
            entity=company,
            attribute="social_engagement",
            value=payload.get("engagement", {}),
            source="social_intel",
            source_type="mcp",
            confidence=0.8,
            now_str=now_str,
        )

        # Timeline
        _emit(
            evidence_list,
            entity=company,
            attribute="social_timeline_events",
            value=payload.get("timeline", []),
            source="social_intel",
            source_type="mcp",
            confidence=0.7,
            now_str=now_str,
        )

        # Source credibility
        _emit(
            evidence_list,
            entity=company,
            attribute="social_source_credibility",
            value=payload.get("source_credibility", {}),
            source="social_intel",
            source_type="mcp",
            confidence=0.9,
            now_str=now_str,
        )

        # Discussion URLs
        _emit(
            evidence_list,
            entity=company,
            attribute="social_discussion_urls",
            value=payload.get("discussion_urls", []),
            source="social_intel",
            source_type="mcp",
            confidence=0.6,
            now_str=now_str,
        )

        # Thematic buckets
        for attr, key, conf in [
            ("social_executive_mentions", "executive_mentions", 0.65),
            ("social_product_mentions", "product_mentions", 0.65),
            ("social_customer_pain_points", "customer_pain_points", 0.7),
            ("social_developer_discussions", "developer_discussions", 0.7),
            ("social_hiring_discussions", "hiring_discussions", 0.7),
        ]:
            _emit(
                evidence_list,
                entity=company,
                attribute=attr,
                value=payload.get(key, []),
                source="social_intel",
                source_type="mcp",
                confidence=conf,
                now_str=now_str,
            )

        # Raw JSON payload as a single artifact if needed
        _emit(
            evidence_list,
            entity=company,
            attribute="social_intelligence_payload",
            value=json.dumps(payload),
            source="social_intel",
            source_type="mcp",
            confidence=0.9,
            now_str=now_str,
        )

        return evidence_list