MODEL_REGISTRY = {
    # Orchestration and Utility
    "planner": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "secondary": {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "tertiary":  None,
        "token_budget": 900,
    },
    "entity_extractor": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-8b-instruct"},
        "secondary": None,
        "tertiary":  None,
        "token_budget": 500,
    },
    "event_extractor": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-8b-instruct"},
        "secondary": None,
        "tertiary":  None,
        "token_budget": 1500,
    },
    "section_generator": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "secondary": None,
        "tertiary":  None,
        "token_budget": 3000,
    },
    "cross_provider_reasoning": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "secondary": None,
        "tertiary":  None,
        "token_budget": 2000,
    },
    "theme_detector": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-8b-instruct"},
        "secondary": None,
        "tertiary":  None,
        "token_budget": 500,
    },
    "news_agent": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "secondary": {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "tertiary":  None,
        "token_budget": 900,
    },
    "technology_agent": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "secondary": {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "tertiary":  None,
        "token_budget": 900,
    },
    "ui": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "secondary": {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "tertiary":  None,
        "token_budget": 4000,
    },
    "page_composer": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-8b-instruct"},
        "secondary": {"provider": "nvidia", "model": "meta/llama-3.1-8b-instruct"}
    },
    "router": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-8b-instruct"},
        "secondary": None,
        "tertiary":  None,
        "token_budget": 500,
    },

    # Deep Analytics
    "financial_agent": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "secondary": {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "tertiary":  None,
        "token_budget": 1500,
    },
    "competitor_agent": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "secondary": {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "tertiary":  None,
        "token_budget": 1500,
    },
    "industry_agent": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "secondary": {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "tertiary":  None,
        "token_budget": 1500,
    },
    "risk_agent": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "secondary": {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "tertiary":  None,
        "token_budget": 1200,
    },
    "synthesizer": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "secondary": None,
        "tertiary":  None,
        "token_budget": 2200,
    },

    # Advanced Reasoning
    "critic": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "secondary": {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "tertiary":  None,
        "token_budget": 1800,
    },
    "evidence_validator": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "secondary": {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "tertiary":  None,
        "token_budget": 1800,
    },
    "cross_validator": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "secondary": {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "tertiary":  None,
        "token_budget": 1800,
    },
    "gap_detection": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "secondary": {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "tertiary":  None,
        "token_budget": 1200,
    },
    "director": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "secondary": {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "tertiary":  None,
        "token_budget": 1800,
    },
    "planning_verification": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "secondary": {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "tertiary":  None,
        "token_budget": 1500,
    },
    "executive_qa": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "secondary": {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "tertiary":  None,
        "token_budget": 1500,
    },
}
