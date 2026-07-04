from datetime import datetime, timezone
from typing import Dict, List, Optional
from services.research.models import (
    ResearchContext, RawResearchBundle, CompanyProfile, 
    Leadership, Competitor, FinancialData, NewsItem, HiringSignal, Source, EntityResolution, SocialSentiment,
    SourcedValue, CompetitiveAxis, CompetitivePositioning, SWOTAnalysis, ValuationMultiples, RiskFactor,
    CapitalAllocation, ManagementCommentary
)

class ResearchSynthesizer:
    """
    Synthesizes a RawResearchBundle, resolved EntityResolution, and raw metrics
    into a unified, clean ResearchContext.
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

    async def synthesize(
        self, 
        bundle: RawResearchBundle, 
        entity: EntityResolution, 
        sec_data: dict, 
        yf_data: dict,
        reddit_data: dict
    ) -> ResearchContext:
        conflicts = []
        sources_dict = {}

        # Extract raw data from providers
        raw_company_data = bundle.company_raw.get("raw_data", {}) if isinstance(bundle.company_raw, dict) else {}
        raw_web_data = bundle.web_raw.get("raw_data", {}) if isinstance(bundle.web_raw, dict) else {}
        raw_news_data = bundle.news_raw.get("raw_data", {}) if isinstance(bundle.news_raw, dict) else {}
        raw_people_data = bundle.people_raw.get("raw_data", {}) if isinstance(bundle.people_raw, dict) else {}

        raw_data = {
            "entity": entity.model_dump(exclude_none=True) if hasattr(entity, "model_dump") else str(entity),
            "company": raw_company_data,
            "web": raw_web_data,
            "news": raw_news_data,
            "financials": sec_data.get("raw_data", {}),
            "market_data": yf_data.get("raw_data", {}),
            "people": raw_people_data,
            "social": reddit_data.get("raw_data", {})
        }

        from services.artifacts.artifact_writer import ArtifactWriter
        ArtifactWriter.write_json("synthesis/raw_web_data_debug.json", raw_data)

        # Helper to track source citations
        def register_source(title: str, url: str, source_type: str):
            key = (title, url)
            if key not in sources_dict:
                sources_dict[key] = Source(
                    title=title,
                    url=url,
                    source_type=source_type
                )

        # 1. Company Profile
        raw_company = bundle.company_raw
        resolved_name = entity.company_name or raw_company.get("name", "Unknown Corp")
        
        company_src_title = raw_company.get("source_title", "Company Registry")
        company_src_url = raw_company.get("source_url", "https://local")
        register_source(
            title=company_src_title,
            url=company_src_url,
            source_type=raw_company.get("source_type", "official_website")
        )

        comp_website = raw_company.get("website", "")
        best_website = comp_website if (comp_website and "directory.com" not in comp_website) else (entity.website or "")

        raw_hq = raw_company.get("headquarters")
        hq_val = None
        if raw_hq is not None:
            hq_val = SourcedValue(
                value=raw_hq,
                source_ids=[company_src_url],
                confidence=0.9 if raw_company.get("source_type") == "official_website" else 0.6
            )
            
        raw_emp = raw_company.get("employee_count")
        emp_val = None
        if raw_emp is not None:
            emp_val = SourcedValue(
                value=raw_emp,
                source_ids=[company_src_url],
                confidence=0.9 if raw_company.get("source_type") == "official_website" else 0.6
            )

        profile = CompanyProfile(
            name=resolved_name,
            overview=raw_company.get("overview", ""),
            headquarters=hq_val,
            employee_count=emp_val,
            website=best_website,
            founders=raw_company.get("founders", [])
        )

        # 2. Leadership & Competitors Deduplication
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
            if name not in leadership_resolved or (l.get("linkedin_url") and not leadership_resolved[name].linkedin_url):
                leadership_resolved[name] = Leadership(
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

        # 3. Financial Information & Conflict Detection
        raw_financials = bundle.financial_raw.get("financial_reports", [])
        resolved_revenue_annual = "N/A"
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
                if rev and rev != "N/A":
                    revenue_observations[rev] = (src_title, src_type, rep)

            if len(revenue_observations) > 1:
                obs_list = [f"'{rev}' from {info[0]}" for rev, info in revenue_observations.items()]
                conflicts.append(f"Conflict: Revenue figures mismatch. Found: {', '.join(obs_list)}.")
                best_rep = None
                best_score = -1
                for rev, (src_title, src_type, rep) in revenue_observations.items():
                    score = self._get_source_score(src_type)
                    if score > best_score:
                        best_score = score
                        best_rep = rep
                if best_rep:
                    resolved_revenue_annual = best_rep.get("revenue_annual", "N/A")
            elif len(revenue_observations) == 1:
                resolved_revenue_annual = list(revenue_observations.keys())[0]
            else:
                resolved_revenue_annual = raw_financials[0].get("revenue_annual", "N/A")

        financials = FinancialData(
            revenue_history=sec_data.get("revenue_history", {}),
            net_income_history=sec_data.get("net_income_history", {}),
            operating_income_history=sec_data.get("operating_income_history", {}),
            assets_history=sec_data.get("assets_history", {}),
            liabilities_history=sec_data.get("liabilities_history", {}),
            cash_flow_history=sec_data.get("cash_flow_history", {}),
            shares_outstanding_history=sec_data.get("shares_outstanding_history", {}),
            market_cap=yf_data.get("market_cap"),
            pe_ratio=yf_data.get("pe_ratio"),
            current_price=yf_data.get("current_price"),
            fifty_two_week_high=yf_data.get("fifty_two_week_high"),
            fifty_two_week_low=yf_data.get("fifty_two_week_low"),
            revenue_annual=resolved_revenue_annual,
            funding_total="N/A",
            last_round="N/A"
        )

        # 4. Social Sentiment
        social_sentiment = None
        if reddit_data and "top_themes" in reddit_data:
            sentiment_obj = SocialSentiment(
                bullish=reddit_data.get("bullish", 0.0),
                bearish=reddit_data.get("bearish", 0.0),
                neutral=reddit_data.get("neutral", 0.0),
                top_themes=reddit_data.get("top_themes", [])
            )
            social_sentiment = SourcedValue(
                value=sentiment_obj,
                source_ids=["https://reddit.com"],
                confidence=0.7
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
                # Handle Evidence mapped format from HostAgent
                if isinstance(item, dict) and "value" in item and "source_ids" in item:
                    news_val = item["value"]
                    url = news_val.get("url")
                    if url:
                        news_resolved[url] = SourcedValue(
                            value=NewsItem(
                                title=news_val.get("title", ""),
                                url=url,
                                date=news_val.get("date"),
                                snippet=news_val.get("snippet", ""),
                                type=news_val.get("type", "general")
                            ),
                            source_ids=item.get("source_ids", []),
                            confidence=item.get("confidence", 0.5)
                        )
                else:
                    # Handle raw provider format
                    url = item.get("url")
                    if url:
                        news_resolved[url] = SourcedValue(
                            value=NewsItem(
                                title=item.get("title", ""),
                                url=url,
                                date=item.get("date"),
                                snippet=item.get("snippet", ""),
                                type=item.get("type", "general")
                            ),
                            source_ids=["news_provider"],
                            confidence=0.5
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
            
            if conflicts:
                base_score = max(base_score - (0.1 * len(conflicts)), 0.1)
                
            confidence_score = round(base_score, 2)
        else:
            confidence_score = 0.5

        # Blending candidate confidence (avoid blending if it is a generic mock entity)
        if entity.ticker and "MOCK" not in entity.ticker and entity.exchange != "UNKNOWN":
            confidence_score = round((confidence_score + entity.confidence) / 2.0, 2)

        # 9. Consulting fields default/inferred population
        comp_name_lower = resolved_name.lower()
        ticker_clean = (entity.ticker or "").upper()
        
        # 9.1 SWOT
        swot_obj = None

        # 9.2 Competitive Positioning
        comp_pos = None

        # 9.3 Valuation Multiples
        yf_info = yf_data.get("info", {})
        pe = yf_info.get("trailingPE") or yf_info.get("forwardPE")
        ps = yf_info.get("priceToSalesTrailing12Months")
        ev_ebitda = yf_info.get("enterpriseToEbitda")
        
        sector = yf_info.get("sector", "Technology")
        pe_median = 28.5
        ev_ebitda_median = 18.2
        ps_median = 5.2
        
        if sector == "Financial Services":
            pe_median = 14.5
            ev_ebitda_median = 11.0
            ps_median = 2.8
        elif sector == "Healthcare":
            pe_median = 22.0
            ev_ebitda_median = 15.4
            ps_median = 4.1
        elif sector == "Consumer Cyclical":
            pe_median = 18.0
            ev_ebitda_median = 12.5
            ps_median = 1.9
        elif sector == "Communication Services":
            pe_median = 20.2
            ev_ebitda_median = 13.0
            ps_median = 3.1
            
        val_multiples = ValuationMultiples(
            pe_ratio=pe,
            pe_sector_median=pe_median,
            ev_ebitda=ev_ebitda,
            ev_ebitda_sector_median=ev_ebitda_median,
            price_to_sales=ps,
            price_to_sales_sector_median=ps_median
        )

        # 9.4 Risk Factors
        risk_factors = []

        # 9.5 Capital Allocation
        buybacks_hist = sec_data.get("buybacks_history", {})
        dividends_hist = sec_data.get("dividends_history", {})
        capex_hist = sec_data.get("capex_history", {})
        
        buybacks_latest = None
        if buybacks_hist:
            sorted_y = sorted(buybacks_hist.keys())
            buybacks_latest = f"${buybacks_hist[sorted_y[-1]] / 1e9:.1f}B (FY{sorted_y[-1]})"
            
        dividends_latest = None
        if dividends_hist:
            sorted_y = sorted(dividends_hist.keys())
            dividends_latest = f"${dividends_hist[sorted_y[-1]] / 1e9:.1f}B (FY{sorted_y[-1]})"
            
        capex_trend = "Stable"
        if capex_hist:
            sorted_y = sorted(capex_hist.keys())
            if len(sorted_y) >= 2:
                val_prev = capex_hist[sorted_y[-2]]
                val_curr = capex_hist[sorted_y[-1]]
                if val_curr > val_prev * 1.05:
                    capex_trend = f"Increasing (from ${val_prev / 1e9:.1f}B to ${val_curr / 1e9:.1f}B)"
                elif val_curr < val_prev * 0.95:
                    capex_trend = f"Decreasing (from ${val_prev / 1e9:.1f}B to ${val_curr / 1e9:.1f}B)"
                else:
                    capex_trend = f"Flat (around ${val_curr / 1e9:.1f}B)"
            elif len(sorted_y) == 1:
                capex_trend = f"Capital expenditure at ${capex_hist[sorted_y[0]] / 1e9:.1f}B"
                
        cap_alloc = CapitalAllocation(
            buybacks=buybacks_latest,
            dividends=dividends_latest,
            capex_trend=capex_trend if capex_hist else "No capex history available"
        )

        # 9.6 Management Commentary
        management_commentary = []

        from services.research.models import AnalyticsData
        from services.research.analytics import AnalyticsCalculator
        
        calc = AnalyticsCalculator()
        analytics_result = calc.calculate(sec_data=sec_data, yf_data=yf_data)
        
        analytics = AnalyticsData(
            revenue_growth=analytics_result.get("revenue_growth", {}),
            profit_growth=analytics_result.get("profit_growth", {}),
            cagr=analytics_result.get("cagr", {}),
            debt_equity=analytics_result.get("debt_equity"),
            operating_margin=analytics_result.get("operating_margin", {}),
            net_margin=analytics_result.get("net_margin", {}),
            fcf_margin=analytics_result.get("fcf_margin", {}),
            roa=analytics_result.get("roa", {}),
            roe=analytics_result.get("roe", {}),
            interest_coverage=analytics_result.get("interest_coverage", {})
        )
        
        return ResearchContext(
            entity=entity,
            profile=profile,
            company_profile=profile,
            financials=financials,
            analytics=analytics,
            news=list(news_resolved.values()),
            leadership=list(leadership_resolved.values()),
            competitors=list(competitors_resolved.values()),
            social_sentiment=social_sentiment,
            sources=list(sources_dict.values()),
            conflicts=conflicts,
            confidence_score=confidence_score,
            generated_at=datetime.now(timezone.utc),
            raw_data=raw_data,
            technology_stack=tech_stack,
            hiring_signals=hiring_signals,
            competitive_positioning=comp_pos,
            swot=swot_obj,
            valuation_multiples=val_multiples,
            risk_factors=risk_factors,
            capital_allocation=cap_alloc,
            management_commentary=management_commentary
        )
