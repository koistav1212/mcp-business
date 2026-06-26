MODEL_REGISTRY = {
    # Orchestration and Utility (Groq Primary)
    "planner": {
        "primary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "secondary": {"provider": "openrouter", "model": "qwen/qwen-2.5-72b-instruct"},
        "tertiary": {"provider": "github", "model": "deepseek/DeepSeek-R1"},
        "token_budget": 900
    },
    "entity_extractor": {
        "primary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "secondary": {"provider": "openrouter", "model": "qwen/qwen-2.5-72b-instruct"},
        "tertiary": {"provider": "github", "model": "deepseek/DeepSeek-R1"},
        "token_budget": 500
    },
    "news_agent": {
        "primary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "secondary": {"provider": "openrouter", "model": "qwen/qwen-2.5-72b-instruct"},
        "tertiary": {"provider": "github", "model": "deepseek/DeepSeek-R1"},
        "token_budget": 900
    },
    "technology_agent": {
        "primary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "secondary": {"provider": "openrouter", "model": "qwen/qwen-2.5-72b-instruct"},
        "tertiary": {"provider": "github", "model": "deepseek/DeepSeek-R1"},
        "token_budget": 900
    },
    "ui": {
        "primary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "secondary": {"provider": "openrouter", "model": "qwen/qwen-2.5-72b-instruct"},
        "tertiary": {"provider": "github", "model": "deepseek/DeepSeek-R1"},
        "token_budget": 4000
    },
    "router": {
        "primary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "secondary": {"provider": "openrouter", "model": "qwen/qwen-2.5-72b-instruct"},
        "tertiary": {"provider": "github", "model": "deepseek/DeepSeek-R1"},
        "token_budget": 500
    },

    # Deep Analytics (OpenRouter Primary)
    "financial_agent": {
        "primary": {"provider": "openrouter", "model": "deepseek/deepseek-chat-v3"},
        "secondary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "tertiary": {"provider": "github", "model": "deepseek/DeepSeek-R1"},
        "token_budget": 1500
    },
    "competitor_agent": {
        "primary": {"provider": "openrouter", "model": "qwen/qwen3-235b-a22b"},
        "secondary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "tertiary": {"provider": "github", "model": "deepseek/DeepSeek-R1"},
        "token_budget": 1500
    },
    "industry_agent": {
        "primary": {"provider": "openrouter", "model": "deepseek/deepseek-chat-v3"},
        "secondary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "tertiary": {"provider": "github", "model": "deepseek/DeepSeek-R1"},
        "token_budget": 1500
    },
    "risk_agent": {
        "primary": {"provider": "openrouter", "model": "qwen/qwen3-235b-a22b"},
        "secondary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "tertiary": {"provider": "github", "model": "deepseek/DeepSeek-R1"},
        "token_budget": 1200
    },
    "synthesizer": {
        "primary": {"provider": "openrouter", "model": "anthropic/claude-sonnet-4"},
        "secondary": {"provider": "github", "model": "deepseek/DeepSeek-R1"},
        "tertiary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "token_budget": 3500
    },

    # Advanced Reasoning (GitHub Models Primary)
    "critic": {
        "primary": {"provider": "github", "model": "deepseek/DeepSeek-R1"},
        "secondary": {"provider": "openrouter", "model": "anthropic/claude-sonnet-4"},
        "tertiary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "token_budget": 1800
    },
    "evidence_validator": {
        "primary": {"provider": "github", "model": "deepseek/DeepSeek-R1"},
        "secondary": {"provider": "openrouter", "model": "anthropic/claude-sonnet-4"},
        "tertiary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "token_budget": 1800
    },
    "cross_validator": {
        "primary": {"provider": "github", "model": "deepseek/DeepSeek-R1"},
        "secondary": {"provider": "openrouter", "model": "anthropic/claude-sonnet-4"},
        "tertiary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "token_budget": 1800
    },
    "gap_detection": {
        "primary": {"provider": "github", "model": "deepseek/DeepSeek-R1"},
        "secondary": {"provider": "openrouter", "model": "anthropic/claude-sonnet-4"},
        "tertiary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "token_budget": 1200
    },
    "director": {
        "primary": {"provider": "github", "model": "deepseek/DeepSeek-R1"},
        "secondary": {"provider": "openrouter", "model": "anthropic/claude-sonnet-4"},
        "tertiary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "token_budget": 1800
    },
    "planning_verification": {
        "primary": {"provider": "github", "model": "deepseek/DeepSeek-R1"},
        "secondary": {"provider": "openrouter", "model": "anthropic/claude-sonnet-4"},
        "tertiary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "token_budget": 1500
    },
    "executive_qa": {
        "primary": {"provider": "github", "model": "deepseek/DeepSeek-R1"},
        "secondary": {"provider": "openrouter", "model": "anthropic/claude-sonnet-4"},
        "tertiary": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "token_budget": 1500
    }
}
