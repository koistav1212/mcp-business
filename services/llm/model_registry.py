MODEL_REGISTRY = {
    # Orchestration and Utility
    "planner": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "secondary": {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "tertiary":  None,
        "token_budget": 900,
    },
    "entity_extractor": {
        "primary":   {"provider": "nvidia", "model": "meta/llama-3.1-70b-instruct"},
        "secondary": {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "tertiary":  None,
        "token_budget": 500,
    },
    "news_agent": {
        "primary":   {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "secondary": {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "tertiary":  None,
        "token_budget": 900,
    },
    "technology_agent": {
        "primary":   {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "secondary": {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "tertiary":  None,
        "token_budget": 900,
    },
    "ui": {
        "primary":   {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "secondary": {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "tertiary":  None,
        "token_budget": 4000,
    },
    "router": {
        "primary":   {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "secondary": {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "tertiary":  None,
        "token_budget": 500,
    },

    # Deep Analytics
    "financial_agent": {
        "primary":   {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "secondary": {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "tertiary":  None,
        "token_budget": 1500,
    },
    "competitor_agent": {
        "primary":   {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "secondary": {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "tertiary":  None,
        "token_budget": 1500,
    },
    "industry_agent": {
        "primary":   {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "secondary": {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "tertiary":  None,
        "token_budget": 1500,
    },
    "risk_agent": {
        "primary":   {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "secondary": {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "tertiary":  None,
        "token_budget": 1200,
    },
    "synthesizer": {
        "primary":   {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "secondary": None,
        "tertiary":  None,
        "token_budget": 2200,
    },

    # Advanced Reasoning
    "critic": {
        "primary":   {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "secondary": {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "tertiary":  None,
        "token_budget": 1800,
    },
    "evidence_validator": {
        "primary":   {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "secondary": {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "tertiary":  None,
        "token_budget": 1800,
    },
    "cross_validator": {
        "primary":   {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "secondary": {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "tertiary":  None,
        "token_budget": 1800,
    },
    "gap_detection": {
        "primary":   {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "secondary": {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "tertiary":  None,
        "token_budget": 1200,
    },
    "director": {
        "primary":   {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "secondary": {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "tertiary":  None,
        "token_budget": 1800,
    },
    "planning_verification": {
        "primary":   {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "secondary": {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "tertiary":  None,
        "token_budget": 1500,
    },
    "executive_qa": {
        "primary":   {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "secondary": {"provider": "self_hosted", "model": "qwen3.5:2b"},
        "tertiary":  None,
        "token_budget": 1500,
    },
}
