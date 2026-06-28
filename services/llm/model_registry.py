MODEL_REGISTRY = {
    # Orchestration and Utility
    "planner": {
        "primary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "secondary": {"provider": "openrouter", "model": "google/gemini-2.5-flash:free"},
        "tertiary": {"provider": "openrouter", "model": "deepseek/deepseek-r1:free"},
        "token_budget": 900
    },
    "entity_extractor": {
        "primary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "secondary": {"provider": "openrouter", "model": "google/gemini-2.5-flash:free"},
        "tertiary": {"provider": "openrouter", "model": "deepseek/deepseek-r1:free"},
        "token_budget": 500
    },
    "news_agent": {
        "primary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "secondary": {"provider": "openrouter", "model": "google/gemini-2.5-flash:free"},
        "tertiary": {"provider": "openrouter", "model": "deepseek/deepseek-r1:free"},
        "token_budget": 900
    },
    "technology_agent": {
        "primary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "secondary": {"provider": "openrouter", "model": "google/gemini-2.5-flash:free"},
        "tertiary": {"provider": "openrouter", "model": "deepseek/deepseek-r1:free"},
        "token_budget": 900
    },
    "ui": {
        "primary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "secondary": {"provider": "openrouter", "model": "google/gemini-2.5-flash:free"},
        "tertiary": {"provider": "openrouter", "model": "deepseek/deepseek-r1:free"},
        "token_budget": 4000
    },
    "router": {
        "primary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "secondary": {"provider": "openrouter", "model": "google/gemini-2.5-flash:free"},
        "tertiary": {"provider": "openrouter", "model": "deepseek/deepseek-r1:free"},
        "token_budget": 500
    },

    # Deep Analytics
    "financial_agent": {
        "primary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "secondary": {"provider": "openrouter", "model": "google/gemini-2.5-flash:free"},
        "tertiary": {"provider": "openrouter", "model": "deepseek/deepseek-r1:free"},
        "token_budget": 1500
    },
    "competitor_agent": {
        "primary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "secondary": {"provider": "openrouter", "model": "google/gemini-2.5-flash:free"},
        "tertiary": {"provider": "openrouter", "model": "deepseek/deepseek-r1:free"},
        "token_budget": 1500
    },
    "industry_agent": {
        "primary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "secondary": {"provider": "openrouter", "model": "google/gemini-2.5-flash:free"},
        "tertiary": {"provider": "openrouter", "model": "deepseek/deepseek-r1:free"},
        "token_budget": 1500
    },
    "risk_agent": {
        "primary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "secondary": {"provider": "openrouter", "model": "google/gemini-2.5-flash:free"},
        "tertiary": {"provider": "openrouter", "model": "deepseek/deepseek-r1:free"},
        "token_budget": 1200
    },
    "synthesizer": {
        "primary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "secondary": {"provider": "openrouter", "model": "google/gemini-2.5-flash:free"},
        "tertiary": {"provider": "openrouter", "model": "deepseek/deepseek-r1:free"},
        "token_budget": 3500
    },

    # Advanced Reasoning
    "critic": {
        "primary": {"provider": "openrouter", "model": "deepseek/deepseek-r1:free"},
        "secondary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "tertiary": {"provider": "openrouter", "model": "google/gemini-2.5-flash:free"},
        "token_budget": 1800
    },
    "evidence_validator": {
        "primary": {"provider": "openrouter", "model": "deepseek/deepseek-r1:free"},
        "secondary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "tertiary": {"provider": "openrouter", "model": "google/gemini-2.5-flash:free"},
        "token_budget": 1800
    },
    "cross_validator": {
        "primary": {"provider": "openrouter", "model": "deepseek/deepseek-r1:free"},
        "secondary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "tertiary": {"provider": "openrouter", "model": "google/gemini-2.5-flash:free"},
        "token_budget": 1800
    },
    "gap_detection": {
        "primary": {"provider": "openrouter", "model": "deepseek/deepseek-r1:free"},
        "secondary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "tertiary": {"provider": "openrouter", "model": "google/gemini-2.5-flash:free"},
        "token_budget": 1200
    },
    "director": {
        "primary": {"provider": "openrouter", "model": "deepseek/deepseek-r1:free"},
        "secondary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "tertiary": {"provider": "openrouter", "model": "google/gemini-2.5-flash:free"},
        "token_budget": 1800
    },
    "planning_verification": {
        "primary": {"provider": "openrouter", "model": "deepseek/deepseek-r1:free"},
        "secondary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "tertiary": {"provider": "openrouter", "model": "google/gemini-2.5-flash:free"},
        "token_budget": 1500
    },
    "executive_qa": {
        "primary": {"provider": "openrouter", "model": "deepseek/deepseek-r1:free"},
        "secondary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "tertiary": {"provider": "openrouter", "model": "google/gemini-2.5-flash:free"},
        "token_budget": 1500
    }
}
