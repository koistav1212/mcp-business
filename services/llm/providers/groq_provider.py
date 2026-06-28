import json
import httpx
import asyncio
import time
import logging
from services.llm.base_provider import BaseProvider
from services.llm.request import LLMRequest
from services.llm.response import LLMResponse

logger = logging.getLogger("uvicorn.error")

try:
    from services.llm.rate_limiter import GROQ_SEMAPHORE
except ImportError:
    GROQ_SEMAPHORE = asyncio.Semaphore(2)

class GroqProvider(BaseProvider):
    def __init__(self, api_key: str, timeout: float = 30.0):
        self.api_key = api_key
        self.timeout = timeout
        self.provider_name = "groq"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        start_time = time.time()
        
        system_prompt = request.system_prompt + "\n\nReturn ONLY valid JSON.\nNo markdown.\nNo explanations."
        
        payload = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": request.temperature
        }
        
        if request.messages:
            payload["messages"].extend(request.messages)
            
        if request.max_tokens is not None:
            payload["max_completion_tokens"] = request.max_tokens
        
        headers = {
            "Authorization": f"Bearer {self.api_key}", 
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with GROQ_SEMAPHORE:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
            
            response.raise_for_status()
            data = response.json()
            
            latency_ms = (time.time() - start_time) * 1000
            
            raw_usage = data.get("usage", {})
            normalized_usage = {
                "prompt_tokens": int(raw_usage.get("prompt_tokens") or 0),
                "completion_tokens": int(raw_usage.get("completion_tokens") or 0),
                "total_tokens": int(raw_usage.get("total_tokens") or 0)
            }
            
            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                usage=normalized_usage,
                provider=self.provider_name,
                model=request.model,
                latency_ms=latency_ms,
                finish_reason=data["choices"][0].get("finish_reason", "stop")
            )
