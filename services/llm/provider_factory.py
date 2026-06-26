import logging
from typing import Optional
from core.config import settings
from services.llm.base_provider import BaseProvider
from services.llm.providers.groq_provider import GroqProvider
from services.llm.providers.openrouter_provider import OpenRouterProvider
from services.llm.providers.github_provider import GithubModelsProvider

logger = logging.getLogger("uvicorn.error")

class ProviderFactory:
    _instances = {}

    @classmethod
    def get_provider(cls, provider_name: str) -> Optional[BaseProvider]:
        provider_name = provider_name.lower()
        if provider_name in cls._instances:
            return cls._instances[provider_name]

        provider = None
        if provider_name == "groq":
            key = settings.GROQ_API_KEY.strip()
            if key and key != "sk-placeholder":
                provider = GroqProvider(api_key=key)
        elif provider_name == "openrouter":
            key = settings.OPENROUTER_API_KEY.strip()
            if key and key != "sk-placeholder":
                provider = OpenRouterProvider(api_key=key)
        elif provider_name == "github":
            # The .env variable requested by the user is github_token, which Maps to GITHUB_TOKEN in Settings
            key = settings.GITHUB_TOKEN.strip()
            if key and key != "sk-placeholder":
                provider = GithubModelsProvider(api_key=key)

        if provider:
            cls._instances[provider_name] = provider
            return provider
            
        logger.warning(f"Failed to instantiate provider: {provider_name}. Missing or invalid API key.")
        return None
