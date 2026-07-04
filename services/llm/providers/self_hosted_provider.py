import os
import time
import httpx
import logging
from core.config import settings
from services.llm.base_provider import BaseProvider
from services.llm.request import LLMRequest
from services.llm.response import LLMResponse

logger = logging.getLogger("uvicorn.error")

async def _call_ollama_text(model: str, system_prompt: str, user_prompt: str, timeout: float = 60.0, **kwargs) -> str:
    """Paragraph helper for agents like planner, synthesizer, etc."""
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": kwargs.get("temperature", 0.2),
    }
    headers = {"Content-Type": "application/json", "Authorization": "Bearer ollama"}
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        content = data["choices"][0].get("message", {}).get("content", "")
        if not content:
            content = data["choices"][0].get("message", {}).get("reasoning", "")
        return content

async def _call_ollama_json(model: str, system_prompt: str, user_prompt: str, timeout: float = 60.0, **kwargs) -> dict:
    """JSON helper for JSON agents."""
    text_content = await _call_ollama_text(model, system_prompt, user_prompt, timeout, **kwargs)
    import re
    import json
    
    # Try to parse json from text
    if "<think>" in text_content:
        text_content = re.sub(r'<think>.*?</think>', '', text_content, flags=re.DOTALL)
        
    text_content = text_content.strip()
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text_content, re.DOTALL | re.IGNORECASE)
    if match:
        text_content = match.group(1).strip()
        return json.loads(text_content)
        
    match = re.search(r'(\{.*\}|\[.*\])', text_content, re.DOTALL)
    if match:
        text_content = match.group(1).strip()
        return json.loads(text_content)
        
    if text_content.startswith("```json"):
        text_content = text_content[7:]
    elif text_content.startswith("```"):
        text_content = text_content[3:]
    if text_content.endswith("```"):
        text_content = text_content[:-3]
        
    return json.loads(text_content.strip())

class SelfHostedProvider(BaseProvider):
    def __init__(self, api_key: str = "ollama", timeout: float = 300.0):
        self.api_key = api_key
        self.timeout = timeout
        self.provider_name = "self_hosted"
        self.base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")

    async def generate(self, request: LLMRequest) -> LLMResponse:
        start_time = time.time()
        
        payload = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": request.temperature if request.temperature is not None else 0.2,
        }
        
        if request.messages:
            payload["messages"].extend(request.messages)
            
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"SELF_HOSTED RESP: {data}")
            
            if not data.get("choices"):
                raise RuntimeError(f"No choices returned from self_hosted model. Raw data: {data}")
                
            content = data["choices"][0].get("message", {}).get("content", "")
            if not content:
                # Fall back to reasoning if present
                content = data["choices"][0].get("message", {}).get("reasoning", "")
                
            if not content:
                raise RuntimeError(f"Empty content and reasoning from self_hosted model. Raw data: {data}")
                
            logger.info(f"[self_hosted raw] {content[:300]}")
            
            latency_ms = (time.time() - start_time) * 1000
            
            raw_usage = data.get("usage", {})
            normalized_usage = {
                "prompt_tokens": int(raw_usage.get("prompt_tokens") or 0),
                "completion_tokens": int(raw_usage.get("completion_tokens") or 0),
                "total_tokens": int(raw_usage.get("total_tokens") or 0)
            }
            
            return LLMResponse(
                content=content,
                usage=normalized_usage,
                provider=self.provider_name,
                model=request.model,
                latency_ms=latency_ms,
                finish_reason=data["choices"][0].get("finish_reason", "stop")
            )
