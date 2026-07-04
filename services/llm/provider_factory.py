import logging
from typing import Optional
from core.config import settings
from services.llm.base_provider import BaseProvider
from services.llm.providers.nvidia_provider import NVIDIAProvider
from services.llm.providers.self_hosted_provider import SelfHostedProvider

logger = logging.getLogger("uvicorn.error")

class ProviderFactory:
    _instances = {}

    @classmethod
    def get_provider(cls, provider_name: str) -> Optional[BaseProvider]:
        provider_name = provider_name.lower()
        if provider_name in cls._instances:
            return cls._instances[provider_name]

        provider = None
        if provider_name == "nvidia":
            key = settings.NVDA_KEY.strip()
            if key and key != "sk-placeholder":
                provider = NVIDIAProvider(api_key=key)
        elif provider_name == "self_hosted":
            provider = SelfHostedProvider()

        if provider:
            cls._instances[provider_name] = provider
            return provider
            
        logger.warning(f"Failed to instantiate provider: {provider_name}. Missing or invalid API key.")
        return None
