import json
import logging
import asyncio
import re
from typing import Optional, Dict, Any, List
from services.llm.request import LLMRequest
from services.llm.response import LLMResponse
from services.llm.model_registry import MODEL_REGISTRY
from services.llm.provider_factory import ProviderFactory

import httpx
logger = logging.getLogger("uvicorn.error")

async def _call_self_hosted_text(model: str, system_prompt: str, user_prompt: str, timeout: float = 300.0) -> str:
    """
    Calls a self_hosted OpenAI-compatible endpoint (e.g., Ollama) and
    returns plain text. Uses `content` first, falls back to `reasoning`
    if present. Raises on timeout or empty output.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            "http://localhost:11434/v1/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 4096,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    choice = data["choices"][0]["message"]
    content = choice.get("content") or ""
    reasoning = choice.get("reasoning") or ""

    text = content.strip() or reasoning.strip()
    if not text:
        raise RuntimeError(f"Empty response from self_hosted model: {data}")

    return text


def extract_json(text: str) -> dict:
    if "<think>" in text:
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        
    text = text.strip()
    
    # Try to extract from markdown code blocks
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()
        return json.loads(text)
        
    # Try to find the first JSON object or array
    match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
    if match:
        text = match.group(1).strip()
        return json.loads(text)
        
    # Fallback to the original logic
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
        
    return json.loads(text)

class ProviderRouter:
    @classmethod
    async def generate_text(cls, agent_name: str, system_prompt: str, user_prompt: str, messages: Optional[List[Dict[str, str]]] = None) -> str:
        """
        Main entrypoint for Agents to generate text using the resilient multi-provider routing.
        """
        registry_entry = MODEL_REGISTRY.get(agent_name, MODEL_REGISTRY.get("router")) # Fallback to generic router config
        token_budget = registry_entry.get("token_budget", 1500)
        
        from services.artifacts.artifact_writer import ArtifactWriter

        fallback_chain = ["primary", "secondary", "tertiary"]

        for priority in fallback_chain:
            config = registry_entry.get(priority)
            if not config:
                continue
                
            provider_name = config["provider"]
            model_name = config["model"]
            
            if provider_name == "self_hosted":
                timeout = 600.0 if agent_name == "synthesizer" else 300.0
                try:
                    logger.info(f"LLM Routing (Text) -> Agent: {agent_name} | Provider: {provider_name} | Model: {model_name} | text helper")
                    raw_text = await _call_self_hosted_text(model_name, system_prompt, user_prompt, timeout=timeout)
                    ArtifactWriter.write_json(f"agent_outputs/{agent_name}_text.json", {
                        "raw_llm_response": raw_text,
                        "validation_result": "success",
                        "errors": []
                    })
                    return raw_text
                except Exception as e:
                    logger.warning(f"Provider {provider_name} failed for {agent_name}: {repr(e)}. Retrying next in chain...")
                    continue
            
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
            
            # Save Input Artifact
            ArtifactWriter.write_json(f"agent_inputs/{agent_name}_text.json", {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "messages": messages or [],
                "token_estimate": token_budget,
                "provider": provider_name,
                "model": model_name
            })
            
            base_delay = 2.0
            attempt = 0
            while True:
                try:
                    logger.info(f"LLM Routing (Text) -> Agent: {agent_name} | Provider: {provider_name} | Model: {model_name} | Attempt: {attempt+1}")
                    
                    response: LLMResponse = await provider.generate(request)
                    
                    # Log telemetry
                    logger.info(
                        f"Telemetry [{agent_name}] -> Provider: {response.provider} | Model: {response.model} | "
                        f"Tokens (In/Out): {response.usage.get('prompt_tokens', 0)}/{response.usage.get('completion_tokens', 0)} | "
                        f"Latency: {response.latency_ms:.2f}ms"
                    )
                    
                    # Save Output Artifact (Success)
                    ArtifactWriter.write_json(f"agent_outputs/{agent_name}_text.json", {
                        "raw_llm_response": response.content,
                        "validation_result": "success",
                        "execution_time": response.latency_ms,
                        "errors": []
                    })
                    
                    return response.content
                        
                except Exception as e:
                    error_msg = str(e).lower()
                    error_type = str(type(e)).lower()
                    
                    # Save Output Artifact (Failure)
                    ArtifactWriter.write_json(f"agent_outputs/{agent_name}_text_error_{attempt}.json", {
                        "raw_llm_response": getattr(response, 'content', None) if 'response' in locals() else None,
                        "validation_result": "failed",
                        "execution_time": getattr(response, 'latency_ms', None) if 'response' in locals() else None,
                        "errors": [str(e)]
                    })
                    
                    is_validation = "validation" in error_msg or "validationerror" in error_type
                    is_429 = "429" in error_msg
                    
                    if is_validation:
                        logger.error(f"Provider {provider_name} validation error for {agent_name}. Failing fast: {repr(e)}")
                        break  # No retries for validation error, fall back immediately
                        
                    if is_429:
                        if attempt >= 1:
                            logger.warning(f"Provider {provider_name} exhausted 429 retries for {agent_name}. Falling back.")
                            break
                        logger.warning(f"Provider {provider_name} rate limited for {agent_name}. Retrying...")
                    else:
                        if attempt >= 2:
                            logger.warning(f"Provider {provider_name} exhausted retries for {agent_name}. Falling back.")
                            break
                        logger.warning(f"Provider {provider_name} failed for {agent_name}: {repr(e)}. Retrying...")
                    
                    attempt += 1
                    await asyncio.sleep(base_delay * (2 ** attempt))
                    
        raise Exception(f"All providers exhausted for agent: {agent_name}. Routing failed.")

    @classmethod
    async def generate_json(cls, agent_name: str, system_prompt: str, user_prompt: str, messages: Optional[List[Dict[str, str]]] = None) -> dict:
        """
        Main entrypoint for Agents to generate JSON using the resilient multi-provider routing.
        """
        registry_entry = MODEL_REGISTRY.get(agent_name, MODEL_REGISTRY.get("router")) # Fallback to generic router config
        token_budget = registry_entry.get("token_budget", 1500)
        
        from services.artifacts.artifact_writer import ArtifactWriter

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
            
            # Save Input Artifact
            ArtifactWriter.write_json(f"agent_inputs/{agent_name}.json", {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "messages": messages or [],
                "token_estimate": token_budget,
                "provider": provider_name,
                "model": model_name
            })
            
            base_delay = 2.0
            attempt = 0
            while True:
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
                        parsed = json.loads(response.content)
                    except json.JSONDecodeError:
                        parsed = extract_json(response.content)
                        
                    # Save Output Artifact (Success)
                    ArtifactWriter.write_json(f"agent_outputs/{agent_name}.json", {
                        "raw_llm_response": response.content,
                        "parsed_json": parsed,
                        "validation_result": "success",
                        "execution_time": response.latency_ms,
                        "errors": []
                    })
                    
                    return parsed
                        
                except Exception as e:
                    error_msg = str(e).lower()
                    error_type = str(type(e)).lower()
                    
                    # Save Output Artifact (Failure)
                    ArtifactWriter.write_json(f"agent_outputs/{agent_name}_error_{attempt}.json", {
                        "raw_llm_response": getattr(response, 'content', None) if 'response' in locals() else None,
                        "parsed_json": None,
                        "validation_result": "failed",
                        "execution_time": getattr(response, 'latency_ms', None) if 'response' in locals() else None,
                        "errors": [str(e)]
                    })
                    
                    is_validation = "validation" in error_msg or "validationerror" in error_type
                    is_429 = "429" in error_msg
                    
                    if is_validation:
                        logger.error(f"Provider {provider_name} validation error for {agent_name}. Failing fast: {repr(e)}")
                        break  # No retries for validation error, fall back immediately
                        
                    if is_429:
                        if attempt >= 1:
                            logger.warning(f"Provider {provider_name} exhausted 429 retries for {agent_name}. Falling back.")
                            break
                        logger.warning(f"Provider {provider_name} rate limited for {agent_name}. Retrying...")
                    else:
                        if attempt >= 2:
                            logger.warning(f"Provider {provider_name} exhausted retries for {agent_name}. Falling back.")
                            break
                        logger.warning(f"Provider {provider_name} failed for {agent_name}: {repr(e)}. Retrying...")
                    
                    attempt += 1
                    await asyncio.sleep(base_delay * (2 ** attempt))
                    
        raise Exception(f"All providers exhausted for agent: {agent_name}. Routing failed.")
