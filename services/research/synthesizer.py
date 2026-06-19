from datetime import datetime, timezone
from typing import Dict, List, Optional
from services.research.models import (
    ResearchContext, RawResearchBundle, CompanyProfile, 
    LeadershipMember, Competitor, FinancialInfo, NewsItem, HiringSignal, Source
)

class ResearchSynthesizer:
    """
    Synthesizes a RawResearchBundle into a unified, clean ResearchContext.
    Handles entity resolution, deduplication, conflict detection, source ranking, and confidence scoring.
    """
    
    # Source type credibility points
    SOURCE_RANKINGS = {
        "official_filing": 10,
        "official_website": 9,
        "professional_network": 8,
        "careers_portal": 8,
        "news_outlet": 7,
        "commercial_database": 6,
        "web_scraper": 5,
        "directory": 3
    }

    def _get_source_score(self, source_type: str) -> int:
        return self.SOURCE_RANKINGS.get(source_type.lower(), 4)

    async def synthesize(self, bundle: RawResearchBundle) -> ResearchContext:
        conflicts = []
        sources_dict = {}

        # Helper to track source citations
        def register_source(title: str, url: str, source_type: str):
            key = (title, url)
            if key not in sources_dict:
                sources_dict[key] = Source(
                    title=title,
                    url=url,
                    source_type=source_type
                )

        # 1. Entity Resolution (Normalize name based on company data)
        raw_company = bundle.company_raw
        resolved_name = raw_company.get("name", "Unknown Corp")
        
        # Register company source
        register_source(
            title=raw_company.get("source_title", "Company Registry"),
            url=raw_company.get("source_url", "https://local"),
            source_type=raw_company.get("source_type", "official_website")
        )

        # 2. Company Profile
        profile = CompanyProfile(
            name=resolved_name,
            overview=raw_company.get("overview", ""),
            headquarters=raw_company.get("headquarters", "Unknown"),
            employee_count=raw_company.get("employee_count", 0),
            website=raw_company.get("website", "")
        )

        # 3. Leadership & Competitors Deduplication
        raw_leaders = raw_company.get("leadership", [])
        raw_people = bundle.people_raw
        if raw_people:
            raw_leaders.extend(raw_people.get("leadership", []))
            register_source(
                title=raw_people.get("source_title", "Talent Directory"),
                url=raw_people.get("source_url", "https://local"),
                source_type=raw_people.get("source_type", "professional_network")
            )

        leadership_resolved = {}
        for l in raw_leaders:
            name = l["name"]
            # Deduplicate by name, pick the one with linkedin url if available
            if name not in leadership_resolved or (l.get("linkedin_url") and not leadership_resolved[name].linkedin_url):
                leadership_resolved[name] = LeadershipMember(
                    name=name,
                    role=l["role"],
                    linkedin_url=l.get("linkedin_url") or l.get("linkedin")
                )

        competitors_resolved = {}
        for c in raw_company.get("competitors", []):
            name = c["name"]
            competitors_resolved[name] = Competitor(
                name=name,
                website=c["website"],
                segment=c["segment"]
            )

        # 4. Financial Information & Conflict Detection
        raw_financials = bundle.financial_raw.get("financial_reports", [])
        resolved_financial = None
        
        if raw_financials:
            for rep in raw_financials:
                register_source(
                    title=rep.get("source_title", "Financial Source"),
                    url=rep.get("source_url", "https://local"),
                    source_type=rep.get("source_type", "commercial_database")
                )

            # Look for conflicts in revenue data
            revenue_observations = {}
            for rep in raw_financials:
                rev = rep.get("revenue_annual")
                src_title = rep.get("source_title")
                src_type = rep.get("source_type", "commercial_database")
                if rev:
                    revenue_observations[rev] = (src_title, src_type, rep)

            if len(revenue_observations) > 1:
                # Mismatch detected
                obs_list = [f"'{rev}' from {info[0]}" for rev, info in revenue_observations.items()]
                conflicts.append(f"Conflict: Revenue figures mismatch. Found: {', '.join(obs_list)}.")
                
                # Resolve: select the one with the highest credibility source type
                best_rep = None
                best_score = -1
                for rev, (src_title, src_type, rep) in revenue_observations.items():
                    score = self._get_source_score(src_type)
                    if score > best_score:
                        best_score = score
                        best_rep = rep
            else:
                best_rep = raw_financials[0]

            if best_rep:
                resolved_financial = FinancialInfo(
                    revenue_annual=best_rep.get("revenue_annual", "N/A"),
                    funding_total=best_rep.get("funding_total", "N/A"),
                    last_round=best_rep.get("last_round", "N/A")
                )

        # 5. Technology Stack
        raw_web = bundle.web_raw
        tech_stack = []
        if raw_web:
            tech_stack = list(set(raw_web.get("technology_stack", [])))
            register_source(
                title=raw_web.get("source_title", "Web Technologies"),
                url=raw_web.get("source_url", "https://local"),
                source_type=raw_web.get("source_type", "web_scraper")
            )

        # 6. News Deduplication
        raw_news = bundle.news_raw
        news_resolved = {}
        if raw_news:
            register_source(
                title=raw_news.get("source_title", "News Outlet"),
                url=raw_news.get("source_url", "https://local"),
                source_type=raw_news.get("source_type", "news_outlet")
            )
            for item in raw_news.get("news", []):
                url = item["url"]
                news_resolved[url] = NewsItem(
                    title=item["title"],
                    url=item["url"],
                    date=item.get("date"),
                    snippet=item["snippet"],
                    type=item["type"]
                )

        # 7. Hiring Signals
        hiring_signals = []
        if raw_people:
            for job in raw_people.get("hiring_signals", []):
                hiring_signals.append(HiringSignal(
                    role_title=job["role_title"],
                    department=job["department"],
                    location=job["location"]
                ))

        # 8. Confidence Scoring
        if sources_dict:
            total_source_score = sum(self._get_source_score(s.source_type) for s in sources_dict.values())
            avg_source_score = total_source_score / len(sources_dict)
            base_score = min(avg_source_score / 10.0, 1.0)
            
            # Deduct for conflicts to reflect quality uncertainty
            if conflicts:
                base_score = max(base_score - (0.1 * len(conflicts)), 0.1)
                
            confidence_score = round(base_score, 2)
        else:
            confidence_score = 0.5

        return ResearchContext(
            company_profile=profile,
            leadership=list(leadership_resolved.values()),
            competitors=list(competitors_resolved.values()),
            financials=resolved_financial,
            news=list(news_resolved.values()),
            hiring_signals=hiring_signals,
            technology_stack=tech_stack,
            sources=list(sources_dict.values()),
            conflicts=conflicts,
            confidence_score=confidence_score,
            generated_at=datetime.now(timezone.utc)
        )
