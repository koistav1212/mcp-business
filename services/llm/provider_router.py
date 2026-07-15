import os
import json
import logging
import asyncio
import re
from typing import Optional, Dict, Any, List
from services.llm.request import LLMRequest
from services.llm.response import LLMResponse
from services.llm.model_registry import MODEL_REGISTRY
from services.llm.provider_factory import ProviderFactory
from services.llm.providers.self_hosted_provider import build_self_hosted_timeout, sanitize_llm_text

import httpx
logger = logging.getLogger("uvicorn.error")

async def _call_self_hosted_text(model: str, system_prompt: str, user_prompt: str, timeout: float = 300.0, force_json: bool = False) -> str:
    """
    Calls a self_hosted OpenAI-compatible endpoint (e.g., Ollama) and
    returns plain text. Uses `content` first, falls back to `reasoning`
    if present. Raises on timeout or empty output.
    """
    timeout_config = build_self_hosted_timeout(timeout)

    async with httpx.AsyncClient(timeout=timeout_config) as client:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": 0.1 if force_json else 0.3,
                "num_ctx": 16384,
                "num_predict": 8192
            },
            "stream": True
        }
        
        if force_json and "qwen" not in model.lower():
            payload["format"] = "json"
            
        base_url = os.environ["OLLAMA_BASE_URL"]
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]
            
        content_chunks = []
        reasoning_chunks = []
        
        async with client.stream("POST", f"{base_url}/api/chat", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    chunk_data = json.loads(line)
                    
                    if "error" in chunk_data:
                        raise RuntimeError(f"Ollama API Error: {chunk_data['error']}")
                        
                    msg = chunk_data.get("message", {})
                    
                    if "content" in msg and msg["content"]:
                        content_chunks.append(msg["content"])
                        
                    if "reasoning" in msg and msg["reasoning"]:
                        reasoning_chunks.append(msg["reasoning"])
                        
                except json.JSONDecodeError:
                    if not content_chunks and not reasoning_chunks and "<html>" in line.lower():
                        raise RuntimeError(f"Received HTML instead of JSON (possibly Cloudflare error): {line[:200]}")
                    continue
                    
    content = "".join(content_chunks)
    reasoning = "".join(reasoning_chunks)

    text = content.strip() or reasoning.strip()
    if not text:
        raise RuntimeError(f"Empty response from self_hosted model.")

    sanitized_text = sanitize_llm_text(text)
    if not sanitized_text:
        raise RuntimeError(
            f"Self-hosted model returned content that became empty after sanitization. Raw content={content!r} raw reasoning={reasoning!r}"
        )

    return sanitized_text


def extract_json(text: str) -> dict:
    text = sanitize_llm_text(text)
        
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


async def _retry_self_hosted_json_after_parse_failure(
    model: str,
    system_prompt: str,
    user_prompt: str,
    invalid_output: str,
    timeout: float,
) -> str:
    repair_system_prompt = (
        system_prompt
        + "\n\nYour previous reply was invalid because it was not parseable JSON."
        + " Retry now. Output ONLY valid JSON. No prose. No headings. No explanations."
    )
    repair_user_prompt = json.dumps(
        {
            "original_task": user_prompt,
            "previous_invalid_output_excerpt": invalid_output[:1200],
            "repair_instruction": "Return only the corrected JSON object.",
        },
        default=str,
    )
    return await _call_self_hosted_text(
        model,
        repair_system_prompt,
        repair_user_prompt,
        timeout=timeout,
        force_json=True,
    )

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
        seen_configs = set()

        for priority in fallback_chain:
            config = registry_entry.get(priority)
            if not config:
                continue
                
            provider_name = config["provider"]
            model_name = config["model"]
            config_key = (provider_name, model_name)
            if config_key in seen_configs:
                logger.info(f"Router skipped duplicate provider config for {agent_name}: {provider_name}/{model_name}")
                continue
            seen_configs.add(config_key)
            
            if provider_name == "self_hosted":
                timeout = 900.0 if agent_name in {"synthesizer", "executive_qa", "financial_agent", "industry_agent", "competitor_agent", "risk_agent", "technology_agent", "director"} else 300.0
                try:
                    logger.info(f"LLM Routing (Text) -> Agent: {agent_name} | Provider: {provider_name} | Model: {model_name} | text helper")
                    raw_text = await _call_self_hosted_text(model_name, system_prompt, user_prompt, timeout=timeout)
                    ArtifactWriter.write_json(f"agent_outputs/{agent_name}_text.json", {
                        "raw_llm_response": raw_text,
                        "validation_result": "success",
                        "errors": []
                    })
                    return sanitize_llm_text(raw_text)
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
                    
                    return sanitize_llm_text(response.content)
                        
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
        seen_configs = set()

        for priority in fallback_chain:
            config = registry_entry.get(priority)
            if not config:
                continue
                
            provider_name = config["provider"]
            model_name = config["model"]
            config_key = (provider_name, model_name)
            if config_key in seen_configs:
                logger.info(f"Router skipped duplicate provider config for {agent_name}: {provider_name}/{model_name}")
                continue
            seen_configs.add(config_key)
            
            if provider_name == "self_hosted":
                timeout = 900.0 if agent_name in {"synthesizer", "executive_qa", "financial_agent", "industry_agent", "competitor_agent", "risk_agent", "technology_agent", "director"} else 300.0
                try:
                    logger.info(f"LLM Routing (JSON) -> Agent: {agent_name} | Provider: {provider_name} | Model: {model_name} | text helper")
                    raw_text = await _call_self_hosted_text(model_name, system_prompt, user_prompt, timeout=timeout, force_json=True)
                    ArtifactWriter.write_json(f"agent_outputs/{agent_name}_self_hosted_raw.json", {
                        "provider": provider_name,
                        "model": model_name,
                        "raw_llm_response": raw_text,
                        "validation_result": "received_unparsed",
                        "errors": []
                    })
                    try:
                        parsed = json.loads(sanitize_llm_text(raw_text))
                    except json.JSONDecodeError:
                        try:
                            parsed = extract_json(raw_text)
                        except json.JSONDecodeError:
                            repaired_text = await _retry_self_hosted_json_after_parse_failure(
                                model_name,
                                system_prompt,
                                user_prompt,
                                raw_text,
                                timeout,
                            )
                            ArtifactWriter.write_json(f"agent_outputs/{agent_name}_self_hosted_repair_raw.json", {
                                "provider": provider_name,
                                "model": model_name,
                                "raw_llm_response": repaired_text,
                                "validation_result": "received_repair_unparsed",
                                "errors": []
                            })
                            parsed = extract_json(repaired_text)
                    ArtifactWriter.write_json(f"agent_outputs/{agent_name}.json", {
                        "raw_llm_response": raw_text,
                        "parsed_json": parsed,
                        "validation_result": "success",
                        "errors": []
                    })
                    return parsed
                except Exception as e:
                    ArtifactWriter.write_json(f"agent_outputs/{agent_name}_self_hosted_parse_error.json", {
                        "provider": provider_name,
                        "model": model_name,
                        "raw_llm_response": locals().get("raw_text"),
                        "validation_result": "failed",
                        "errors": [repr(e)]
                    })
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
                        parsed = json.loads(sanitize_llm_text(response.content))
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
