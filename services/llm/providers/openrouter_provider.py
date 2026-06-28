import time
import httpx
from services.llm.base_provider import BaseProvider
from services.llm.request import LLMRequest
from services.llm.response import LLMResponse

class OpenRouterProvider(BaseProvider):
    def __init__(self, api_key: str, timeout: float = 60.0):
        self.api_key = api_key
        self.timeout = timeout
        self.provider_name = "openrouter"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        start_time = time.time()
        
        payload = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "response_format": {"type": "json_object"},
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
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
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
