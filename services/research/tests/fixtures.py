from services.research.models import EntityResolution, EntityCore

MOCK_COMPANY_RESPONSES = {
    "zoho": {
        "company": {
            "source_title": "Zoho Official About Page",
            "source_url": "https://zoho.com/about-us",
            "source_type": "official_website",
            "name": "Zoho Corporation",
            "overview": "Zoho Corporation is a global technology company providing online business suites and SaaS.",
            "headquarters": "Chennai, India & Austin, Texas",
            "employee_count": 12000,
            "website": "https://zoho.com",
            "founders": ["Sridhar Vembu", "Tony Thomas"],
            "leadership": [
                {"name": "Sridhar Vembu", "role": "CEO & Founder", "linkedin_url": "https://linkedin.com/in/sridharvembu"},
                {"name": "Radha Vembu", "role": "Product Suite Leader", "linkedin_url": None}
            ],
            "competitors": [
                {"name": "Salesforce", "website": "https://salesforce.com", "segment": "CRM & Enterprise"},
                {"name": "HubSpot", "website": "https://hubspot.com", "segment": "SMB Marketing & CRM"}
            ],
            "raw_data": {"note": "Mocked Zoho company profile for testing."}
        },
        "news": {
            "source_title": "TechCrunch Enterprise News Feed",
            "source_url": "https://techcrunch.com/company/zoho",
            "source_type": "news_outlet",
            "news": [
                {
                    "title": "Zoho launches new AI-driven CRM tools",
                    "url": "https://techcrunch.com/zoho-ai-crm",
                    "date": "2026-05-15",
                    "snippet": "Zoho Corporation announced today its latest suite of AI integrations for its flagship CRM platform.",
                    "type": "product_launch"
                },
                {
                    "title": "How Zoho bootstrapped to a billion-dollar valuation",
                    "url": "https://forbes.com/zoho-billion",
                    "date": "2025-10-01",
                    "snippet": "An inside look at how Zoho founder Sridhar Vembu built a global tech giant without raising any venture capital.",
                    "type": "investment"
                }
            ],
            "raw_data": {"note": "Mocked Zoho news for testing compatibility."}
        },
        "market": {
            "market_cap": None,
            "pe_ratio": None,
            "current_price": None,
            "fifty_two_week_high": None,
            "fifty_two_week_low": None,
            "raw_data": {"note": "Mocked Zoho market data."}
        },
        "people": {
            "source_title": "LinkedIn Professional Network Directory",
            "source_url": "https://linkedin.com/company/zoho",
            "source_type": "professional_network",
            "leadership": [
                {"name": "Sridhar Vembu", "role": "CEO & Founder", "linkedin_url": "https://linkedin.com/in/sridharvembu"},
                {"name": "Radha Vembu", "role": "Product Leader", "linkedin_url": "https://linkedin.com/in/radhavembu"}
            ],
            "hiring_signals": [
                {"role_title": "Senior React Developer", "department": "Engineering", "location": "Chennai, India"},
                {"role_title": "AI Research Engineer", "department": "R&D", "location": "Austin, Texas"}
            ]
        },
        "technology": {
            "source_title": "BuiltWith Web Technologies Report",
            "source_url": "https://builtwith.com/zoho.com",
            "source_type": "web_scraper",
            "technology_stack": ["Java", "Deluge Script", "React", "PostgreSQL", "Nginx", "Docker"]
        },
        "entity_resolution": [
            EntityResolution(
                entity=EntityCore(
                    name="Zoho Corporation",
                    ticker="PRIVATE",
                    cik=None,
                    exchange="PRIVATE",
                    website="zoho.com",
                ),
                metadata={
                    "confidence": 0.95
                }
            )
        ],
        "social": {
            "bullish": 45.0,
            "bearish": 10.0,
            "neutral": 45.0,
            "top_themes": ["SaaS Bootstrapping", "Privacy Features", "Zoho One Adoption"],
            "raw_data": {"source": "r/technology & r/india threads"}
        }
    },
    "google": {
        "company": {
            "source_title": "Alphabet Investor Relations",
            "source_url": "https://abc.xyz",
            "source_type": "press_release",
            "name": "Google LLC",
            "overview": "Google is a multi-national tech conglomerate focusing on search, cloud, and digital advertising.",
            "headquarters": "Mountain View, California",
            "employee_count": 182000,
            "website": "https://google.com",
            "founders": ["Larry Page", "Sergey Brin"],
            "leadership": [
                {"name": "Sundar Pichai", "role": "CEO", "linkedin_url": "https://linkedin.com/in/sundarpichai"}
            ],
            "competitors": [
                {"name": "Microsoft", "website": "https://microsoft.com", "segment": "Cloud & Office Suite"}
            ],
            "raw_data": {"note": "Mocked Google company profile for testing."}
        },
        "news": {
            "source_title": "Wired Tech Portal",
            "source_url": "https://wired.com/tag/google",
            "source_type": "news_outlet",
            "news": [
                {
                    "title": "Google announces major updates to its AI search experience",
                    "url": "https://wired.com/google-search-ai",
                    "date": "2026-06-01",
                    "snippet": "At its annual conference, Google unveiled several enhancements to its core search engine.",
                    "type": "product_launch"
                }
            ],
            "raw_data": {"note": "Mocked Google news for testing compatibility."}
        },
        "market": {
            "market_cap": None,
            "pe_ratio": None,
            "current_price": None,
            "fifty_two_week_high": None,
            "fifty_two_week_low": None,
            "raw_data": {"note": "No ticker symbol resolved or private company."}
        },
        "people": {
            "source_title": "Google Careers Portal",
            "source_url": "https://careers.google.com/jobs",
            "source_type": "careers_portal",
            "leadership": [
                {"name": "Sundar Pichai", "role": "CEO", "linkedin_url": "https://linkedin.com/in/sundarpichai"},
                {"name": "Demis Hassabis", "role": "CEO, Google DeepMind", "linkedin_url": "https://linkedin.com/in/demishassabis"}
            ],
            "hiring_signals": [
                {"role_title": "Staff Software Engineer, Gemini", "department": "AI DeepMind", "location": "London, UK"}
            ]
        },
        "technology": {
            "source_title": "StackShare Engineering Stack",
            "source_url": "https://stackshare.io/google/google",
            "source_type": "web_scraper",
            "technology_stack": ["C++", "Python", "Go", "Spanner", "Angular", "Kubernetes"]
        },
        "entity_resolution": [
            EntityResolution(
                entity=EntityCore(
                    name="Alphabet Inc.",
                    ticker="GOOGL",
                    cik="0001652044",
                    exchange="NASDAQ",
                    website="abc.xyz",
                ),
                metadata={
                    "confidence": 0.99
                }
            )
        ]
    },
    "acme": {
        "company": {
            "source_title": "Generic Web Directory",
            "source_url": "https://directory.com/acmecorp",
            "source_type": "directory",
            "name": "Acmecorp",
            "overview": "Acmecorp is an unverified business entity.",
            "headquarters": "Unknown",
            "employee_count": 100,
            "website": "https://acmecorp.com",
            "founders": [],
            "leadership": [],
            "competitors": [],
            "raw_data": {"note": "Mocked AcmeCorp company profile for testing."}
        },
        "people": {
            "source_title": "Generic Job Bulletin",
            "source_url": "https://jobsbulletin.com/acme",
            "source_type": "directory",
            "leadership": [],
            "hiring_signals": [
                {"role_title": "Customer Success Representative", "department": "Operations", "location": "Remote"}
            ]
        },
        "technology": {
            "source_title": "Wappalyzer Automated Site Probe",
            "source_url": "https://wappalyzer.com/profile/acme.com",
            "source_type": "web_scraper",
            "technology_stack": ["HTML5", "WordPress", "MySQL", "PHP"]
        },
        "entity_resolution": [
            EntityResolution(
                entity=EntityCore(
                    name="Acmecorp",
                    ticker=None,
                    cik=None,
                    exchange=None,
                    website="acmecorp.example.com",
                ),
                metadata={
                    "confidence": 0.5
                }
            )
        ]
    }
}
