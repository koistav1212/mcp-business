import json
import httpx
import asyncio
import re
import logging
import logging
from abc import ABC, abstractmethod
from typing import Optional
from core.config import settings

logger = logging.getLogger("uvicorn.error")

try:
    from services.llm.rate_limiter import GROQ_SEMAPHORE
except ImportError:
    # Fallback if rate_limiter.py doesn't exist yet
    GROQ_SEMAPHORE = asyncio.Semaphore(2)

try:
    from services.core.token_budget import TOKEN_LIMIT
except ImportError:
    TOKEN_LIMIT = {}


def extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    
    if "<think>" in text:
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        
    return json.loads(text)

class BaseLLM(ABC):
    @abstractmethod
    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        pass

class OpenAIProvider(BaseLLM):
    def __init__(self, api_key: str, model: str, timeout: float = 45.0, role: str = None):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.role = role

    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        logger.info(
            f"{getattr(self, 'role', 'Agent')} payload size: "
            f"{len(system_prompt) + len(user_prompt)} chars"
        )
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
            }
            if self.role and self.role in TOKEN_LIMIT:
                payload["max_completion_tokens"] = TOKEN_LIMIT[self.role]
                
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            return json.loads(response.json()["choices"][0]["message"]["content"])

class OpenRouterProvider(BaseLLM):
    def __init__(self, api_key: str, model: str, timeout: float = 60.0, fallback_model: str = None, role: str = None):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.fallback_model = fallback_model
        self.role = role

    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        logger.info(
            f"{getattr(self, 'role', 'Agent')} payload size: "
            f"{len(system_prompt) + len(user_prompt)} chars"
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        if self.role and self.role in TOKEN_LIMIT:
            payload["max_completion_tokens"] = TOKEN_LIMIT[self.role]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                return json.loads(response.json()["choices"][0]["message"]["content"])
            except Exception as e:
                if self.fallback_model:
                    payload["model"] = self.fallback_model
                    response = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    return json.loads(response.json()["choices"][0]["message"]["content"])
                raise e

class GroqProvider(BaseLLM):
    def __init__(self, api_key: str, model: str, timeout: float = 30.0, role: str = None):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.role = role

    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        logger.info(
            f"{getattr(self, 'role', 'Agent')} payload size: "
            f"{len(system_prompt) + len(user_prompt)} chars"
        )
        system_prompt += "\n\nReturn ONLY valid JSON.\nNo markdown.\nNo explanations."
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0
        }
        if self.role and self.role in TOKEN_LIMIT:
            payload["max_completion_tokens"] = TOKEN_LIMIT[self.role]
        
        headers = {
            "Authorization": f"Bearer {self.api_key}", 
            "Content-Type": "application/json"
        }
        
        max_retries = 5
        base_delay = 2.0
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(max_retries):
                try:
                    async with GROQ_SEMAPHORE:
                        response = await client.post(
                            "https://api.groq.com/openai/v1/chat/completions",
                            headers=headers,
                            json=payload,
                        )
                    
                    if response.status_code == 429:
                        retry_after = float(response.headers.get("retry-after", base_delay * (2 ** attempt)))
                        logger.warning(f"Groq API 429 Rate Limit. Retrying in {retry_after}s...")
                        await asyncio.sleep(retry_after)
                        continue
                        
                    if not response.is_success:
                        logger.error(f"Groq Error: {response.text}")
                        response.raise_for_status()
                        
                    content = response.json()["choices"][0]["message"]["content"]
                    
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        return extract_json(content)
                        
                except httpx.HTTPStatusError as e:
                    if attempt == max_retries - 1:
                        raise e
                    if e.response.status_code not in [429, 500, 502, 503, 504]:
                        raise e
                    await asyncio.sleep(base_delay * (2 ** attempt))
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    await asyncio.sleep(base_delay * (2 ** attempt))
            
            raise Exception("Max retries exceeded for Groq API")

class OllamaProvider(BaseLLM):
    def __init__(self, model: str, host: str = "http://localhost:11434", timeout: float = 120.0):
        self.model = model
        self.host = host
        self.timeout = timeout

    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        logger.info(
            f"Ollama payload size: "
            f"{len(system_prompt) + len(user_prompt)} chars"
        )
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "format": "json",
                    "stream": False
                },
            )
            response.raise_for_status()
            return json.loads(response.json()["message"]["content"])


class TogetherProvider(BaseLLM):
    def __init__(self, api_key: str, model: str, timeout: float = 60.0, role: str = None):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.role = role

    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        logger.info(
            f"{getattr(self, 'role', 'Agent')} payload size: "
            f"{len(system_prompt) + len(user_prompt)} chars"
        )
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
            }
            if self.role and self.role in TOKEN_LIMIT:
                payload["max_tokens"] = TOKEN_LIMIT[self.role]
                
            response = await client.post(
                "https://api.together.xyz/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            return json.loads(response.json()["choices"][0]["message"]["content"])


class ModelRouter:
    """
    Routes agent tasks to specific optimized models.
    """
    GROQ_MODELS = {
        "planner": "llama-3.3-70b-versatile",
        "director": "llama-3.3-70b-versatile",
        "competitor_agent": "meta-llama/llama-4-scout-17b-16e-instruct",
        "industry_agent": "meta-llama/llama-4-scout-17b-16e-instruct",
        "news_agent": "meta-llama/llama-4-scout-17b-16e-instruct",
        "financial_agent": "meta-llama/llama-4-scout-17b-16e-instruct",
        "technology_agent": "meta-llama/llama-4-scout-17b-16e-instruct",
        "ai_agent": "llama-3.3-70b-versatile",
        "strategy_agent": "llama-3.3-70b-versatile",
        "synthesizer": "llama-3.3-70b-versatile",
        "critic": "meta-llama/llama-4-scout-17b-16e-instruct",
        "ui": "meta-llama/llama-4-scout-17b-16e-instruct",
        "entity_extractor": "meta-llama/llama-4-scout-17b-16e-instruct"
    }

    TOGETHER_MODELS = {
        "planner": "Qwen/Qwen3-235B-A22B-Instruct-2507",
        "director": "deepseek-ai/DeepSeek-R1",
        "research": "deepseek-ai/DeepSeek-V3",
        "competitor_agent": "deepseek-ai/DeepSeek-V3",
        "industry_agent": "deepseek-ai/DeepSeek-V3",
        "news_agent": "deepseek-ai/DeepSeek-V3",
        "technology_agent": "deepseek-ai/DeepSeek-V3",
        "financial_agent": "deepseek-ai/DeepSeek-V3",
        "ai_agent": "deepseek-ai/DeepSeek-R1",
        "strategy_agent": "deepseek-ai/DeepSeek-R1",
        "synthesizer": "deepseek-ai/DeepSeek-V3",
        "entity_extractor": "Qwen/Qwen3-Coder-480B-A35B-Instruct",
        "ui": "Qwen/Qwen3-Coder-480B-A35B-Instruct",
        "critic": "deepseek-ai/DeepSeek-R1",
    }

    OPENROUTER_MODELS = {
        "planner": "qwen/qwen-2.5-72b-instruct",
        "director": "deepseek/deepseek-r1:free",
        "competitor_agent": "deepseek/deepseek-chat-v3:free",
        "industry_agent": "deepseek/deepseek-chat-v3:free",
        "news_agent": "deepseek/deepseek-chat-v3:free",
        "technology_agent": "deepseek/deepseek-chat-v3:free",
        "financial_agent": "deepseek/deepseek-chat-v3:free",
        "ai_agent": "deepseek/deepseek-r1:free",
        "strategy_agent": "deepseek/deepseek-r1:free",
        "synthesizer": "deepseek/deepseek-r1:free",
        "entity_extractor": "qwen/qwen-2.5-72b-instruct",
        "ui": "qwen/qwen-2.5-coder-32b-instruct",
        "critic": "deepseek/deepseek-r1:free",
        "research": "deepseek/deepseek-chat-v3:free", 
    }

    def _get_provider(self, role: str) -> Optional[BaseLLM]:
        provider_name = settings.LLM_PROVIDER.lower()
        if provider_name == "openrouter":
            model = self.OPENROUTER_MODELS.get(role, settings.LLM_MODEL)
            key = settings.OPENROUTER_API_KEY.strip()
            if key and key != "sk-placeholder":
                logger.info(f"LLM Routing -> Agent: {role} | Provider: {provider_name} | Model: {model}")
                return OpenRouterProvider(key, model, role=role)
        elif provider_name == "groq":
            model = self.GROQ_MODELS.get(role, "llama-3.3-70b-versatile")
            key = settings.GROQ_API_KEY.strip()
            if key and key != "sk-placeholder":
                logger.info(f"LLM Routing -> Agent: {role} | Provider: {provider_name} | Model: {model}")
                return GroqProvider(key, model, role=role)
        elif provider_name == "together":
            model = self.TOGETHER_MODELS.get(role, settings.LLM_MODEL)
            key = settings.TOGETHER_API_KEY.strip()
            if key and key != "sk-placeholder":
                logger.info(f"LLM Routing -> Agent: {role} | Provider: {provider_name} | Model: {model}")
                return TogetherProvider(key, model, role=role)
        elif provider_name == "ollama":
            logger.info(f"LLM Routing -> Agent: {role} | Provider: {provider_name} | Model: {settings.LLM_MODEL}")
            return OllamaProvider(settings.LLM_MODEL)
        else:
            # Fallback to OpenAI
            key = settings.OPENAI_API_KEY.strip()
            if key and key != "sk-placeholder":
                logger.info(f"LLM Routing -> Agent: {role} | Provider: openai | Model: {settings.LLM_MODEL}")
                return OpenAIProvider(key, settings.LLM_MODEL, role=role)
        
        logger.warning(f"LLM Routing -> Agent: {role} | Failed to configure provider: {provider_name}")
        return None

    def get_model_for_role(self, role: str) -> Optional[BaseLLM]:
        return self._get_provider(role)

    def planner(self) -> Optional[BaseLLM]:
        return self._get_provider("planner")
        
    def director(self) -> Optional[BaseLLM]:
        return self._get_provider("director")

    def research(self) -> Optional[BaseLLM]:
        return self._get_provider("research")
        
    def synthesizer(self) -> Optional[BaseLLM]:
        return self._get_provider("synthesizer")

    def ui(self) -> Optional[BaseLLM]:
        return self._get_provider("ui")

    def critic(self) -> Optional[BaseLLM]:
        return self._get_provider("critic")
