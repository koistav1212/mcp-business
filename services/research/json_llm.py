import json
from typing import Optional

import httpx


class OpenAIJSONGenerator:
    """Small async adapter shared by planning and writing layers."""

    def __init__(self, api_key: str, model: str, timeout: float = 45.0):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def __call__(self, system_prompt: str, user_prompt: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            return json.loads(response.json()["choices"][0]["message"]["content"])


def configured_json_generator() -> Optional[OpenAIJSONGenerator]:
    from core.config import settings

    key = settings.OPENAI_API_KEY.strip()
    if not key or key == "sk-placeholder":
        return None
    return OpenAIJSONGenerator(key, settings.LLM_MODEL)
