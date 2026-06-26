import json
import logging
import asyncio
import re
from typing import Optional, Dict, Any, List
from services.llm.request import LLMRequest
from services.llm.response import LLMResponse
from services.llm.model_registry import MODEL_REGISTRY
from services.llm.provider_factory import ProviderFactory

logger = logging.getLogger("uvicorn.error")

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

class ProviderRouter:
    @classmethod
    async def generate_json(cls, agent_name: str, system_prompt: str, user_prompt: str, messages: Optional[List[Dict[str, str]]] = None) -> dict:
        """
        Main entrypoint for Agents to generate JSON using the resilient multi-provider routing.
        """
        registry_entry = MODEL_REGISTRY.get(agent_name, MODEL_REGISTRY.get("router")) # Fallback to generic router config
        token_budget = registry_entry.get("token_budget", 1500)
        
        fallback_chain = ["primary", "secondary", "tertiary"]
        
        for priority in fallback_chain:
            config = registry_entry.get(priority)
            if not config:
                continue
                
            provider_name = config["provider"]
            model_name = config["model"]
            
            provider = ProviderFactory.get_provider(provider_name)
            if not provider:
                logger.warning(f"Router skipped {provider_name} for {agent_name} ({priority}) due to missing configuration.")
                continue
                
            request = LLMRequest(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                messages=messages or [],
                model=model_name,
                max_tokens=token_budget
            )
            
            max_retries = 3
            base_delay = 2.0
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"LLM Routing -> Agent: {agent_name} | Provider: {provider_name} | Model: {model_name} | Attempt: {attempt+1}")
                    
                    response: LLMResponse = await provider.generate(request)
                    
                    # Log telemetry
                    logger.info(
                        f"Telemetry [{agent_name}] -> Provider: {response.provider} | Model: {response.model} | "
                        f"Tokens (In/Out): {response.usage.get('prompt_tokens', 0)}/{response.usage.get('completion_tokens', 0)} | "
                        f"Latency: {response.latency_ms:.2f}ms"
                    )
                    
                    try:
                        return json.loads(response.content)
                    except json.JSONDecodeError:
                        return extract_json(response.content)
                        
                except Exception as e:
                    # Specific handling for rate limits or server errors
                    error_msg = str(e)
                    is_rate_limit = "429" in error_msg
                    
                    if is_rate_limit:
                        logger.warning(f"Provider {provider_name} rate limited for {agent_name}. Retrying...")
                    else:
                        logger.warning(f"Provider {provider_name} failed for {agent_name}: {e}")
                    
                    if attempt == max_retries - 1:
                        logger.warning(f"Provider {provider_name} exhausted retries for {agent_name}. Falling back.")
                        break # Move to next provider in fallback chain
                    
                    await asyncio.sleep(base_delay * (2 ** attempt))
                    
        raise Exception(f"All providers exhausted for agent: {agent_name}. Routing failed.")
