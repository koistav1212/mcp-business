SOURCE_DOMAINS = {
    "news": {
        "news_feed",
        "news_intelligence",
        "news_intelligence_pipeline",
        "google_news",
        "google_news_rss",
        "newsapi",
        "gnews",
        "reuters",
        "reuters_news",
        "yahoo_news",
        "yahoo_finance_news",
        "financial_times",
        "ft_news",
    },
    "financial": {
        "sec_edgar",
        "sec_edgar_10k",
        "yfinance",
        "global_markets",
    },
    "social": {
        "reddit",
        "stocktwits",
        "hackernews",
        "social_intel",
    },
    "technology": {
        "technology_profile",
        "technology_intelligence",
    },
    "profile": {
        "company_profile",
        "crunchbase",
        "similarweb",
        "web_technology_profile"
    },
    "people": {
        "people_pipeline",
        "indeed",
        "github",
        "glassdoor"
    }
}

def resolve_domain(source: str) -> str:
    source = (source or "").lower().strip()
    
    for domain, sources in SOURCE_DOMAINS.items():
        if source in sources:
            return domain
            
    if "news" in source or source.startswith("news_"):
        return "news"
        
    if source.startswith("technology_"):
        return "technology"
        
    if source.startswith("social_intel"):
        return "social"
        
    if source.startswith("company_profile"):
        return "profile"
        
    if source.startswith("sec_edgar"):
        return "financial"
        
    return "unknown"
