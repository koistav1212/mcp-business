import os
import json
import logging
import asyncio
import re
import random
from typing import Optional, Dict, Any, List
from services.llm.request import LLMRequest
from services.llm.response import LLMResponse
from services.llm.model_registry import MODEL_REGISTRY
from services.llm.provider_factory import ProviderFactory
from services.llm.providers.self_hosted_provider import sanitize_llm_text
from json_repair import repair_json
import httpx

logger = logging.getLogger("uvicorn.error")

GLOBAL_LLM_SEMAPHORE = asyncio.Semaphore(2)

def _profile_llm_call(agent_name: str, user_prompt: str, messages: Optional[List[Dict[str, str]]] = None):
    text_content = user_prompt
    if messages:
        text_content += " " + " ".join([m.get("content", "") for m in messages])
    
    char_count = len(text_content)
    token_est = char_count // 4
    evidence_count = text_content.count('"source_id"') + text_content.count("'source_id'")
    url_count = text_content.count('http://') + text_content.count('https://')
    entity_count = text_content.count('"company_name"') + text_content.count('"ticker"')
    
    logger.info(
        f"\nAgent: {agent_name}\n"
        f"Input tokens: {token_est}\n"
        f"Chars: {char_count}\n"
        f"Evidence objects: {evidence_count}\n"
        f"URLs: {url_count}\n"
        f"Entities: {entity_count}\n"
    )

async def _call_openrouter_text(model: str, system_prompt: str, user_prompt: str, timeout: float = 300.0, force_json: bool = False) -> str:
    headers = {
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1 if force_json else 0.3,
        "stream": True
    }
    
    if force_json and "gemma" not in model.lower() and "qwen" not in model.lower():
        payload["response_format"] = {"type": "json_object"}
        
    base_url = "https://openrouter.ai/api/v1"
    
    content_chunks = []
    
    async with GLOBAL_LLM_SEMAPHORE:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", f"{base_url}/chat/completions", json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip() or line.strip() == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        line = line[6:]
                    try:
                        chunk_data = json.loads(line)
                        if "error" in chunk_data:
                            raise RuntimeError(f"OpenRouter API Error: {chunk_data['error']}")
                            
                        choices = chunk_data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                content_chunks.append(delta["content"])
                                
                    except json.JSONDecodeError:
                        continue
                    
    content = "".join(content_chunks)
    text = content.strip()
    if not text:
        raise RuntimeError(f"Empty response from openrouter model.")

    sanitized_text = sanitize_llm_text(text)
    if not sanitized_text:
        raise RuntimeError(f"OpenRouter model returned empty content after sanitization. Raw={content!r}")

    return sanitized_text


def extract_json(text: str) -> dict:
    text = sanitize_llm_text(text)
        
    text = text.strip()
    
    # Try to extract from markdown code blocks
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return json.loads(repair_json(text))
        
    # Try to find the first JSON object or array
    match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
    if match:
        text = match.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return json.loads(repair_json(text))
        
    # Fallback to the original logic
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
        
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(repair_json(text))


async def _retry_openrouter_json_after_parse_failure(
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
    return await _call_openrouter_text(
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
        
        _profile_llm_call(agent_name, user_prompt, messages)

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
            
            if provider_name == "openrouter":
                timeout = 360.0
                base_delay = 2.0
                attempt = 0
                while attempt < 3:
                    try:
                        logger.info(f"LLM Routing (Text) -> Agent: {agent_name} | Provider: {provider_name} | Model: {model_name} | text helper | Attempt: {attempt+1}")
                        raw_text = await _call_openrouter_text(model_name, system_prompt, user_prompt, timeout=timeout)
                        ArtifactWriter.write_json(f"agent_outputs/{agent_name}_text.json", {
                            "raw_llm_response": raw_text,
                            "validation_result": "success",
                            "errors": []
                        })
                        return sanitize_llm_text(raw_text)
                    except Exception as e:
                        attempt += 1
                        if attempt >= 3:
                            logger.warning(f"Provider {provider_name} exhausted 3 attempts for {agent_name}: {repr(e)}. Retrying next in chain...")
                            break
                        logger.warning(f"Provider {provider_name} failed for {agent_name}: {repr(e)}. Retrying attempt {attempt+1}...")
                        await asyncio.sleep(base_delay * (2 ** attempt) + random.uniform(0.1, 1.0))
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
                    
                    async with GLOBAL_LLM_SEMAPHORE:
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
                    is_429 = "429" in error_msg or "502" in error_msg or "503" in error_msg or "504" in error_msg
                    
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
                    await asyncio.sleep(base_delay * (2 ** attempt) + random.uniform(0.1, 1.0))
                    
        raise Exception(f"All providers exhausted for agent: {agent_name}. Routing failed.")

    @classmethod
    async def generate_json(cls, agent_name: str, system_prompt: str, user_prompt: str, messages: Optional[List[Dict[str, str]]] = None) -> dict:
        """
        Main entrypoint for Agents to generate JSON using the resilient multi-provider routing.
        """
        registry_entry = MODEL_REGISTRY.get(agent_name, MODEL_REGISTRY.get("router")) # Fallback to generic router config
        token_budget = registry_entry.get("token_budget", 1500)
        
        from services.artifacts.artifact_writer import ArtifactWriter

        _profile_llm_call(agent_name, user_prompt, messages)

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
            
            if provider_name == "openrouter":
                timeout = 360.0
                base_delay = 2.0
                attempt = 0
                while attempt < 3:
                    try:
                        logger.info(f"LLM Routing (JSON) -> Agent: {agent_name} | Provider: {provider_name} | Model: {model_name} | text helper | Attempt: {attempt+1}")
                        raw_text = await _call_openrouter_text(model_name, system_prompt, user_prompt, timeout=timeout, force_json=True)
                        ArtifactWriter.write_json(f"agent_outputs/{agent_name}_openrouter_raw.json", {
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
                                repaired_text = await _retry_openrouter_json_after_parse_failure(
                                    model_name,
                                    system_prompt,
                                    user_prompt,
                                    raw_text,
                                    timeout,
                                )
                                ArtifactWriter.write_json(f"agent_outputs/{agent_name}_openrouter_repair_raw.json", {
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
                        ArtifactWriter.write_json(f"agent_outputs/{agent_name}_openrouter_parse_error_{attempt}.json", {
                            "provider": provider_name,
                            "model": model_name,
                            "raw_llm_response": locals().get("raw_text"),
                            "validation_result": "failed",
                            "errors": [repr(e)]
                        })
                        attempt += 1
                        if attempt >= 3:
                            logger.warning(f"Provider {provider_name} exhausted 3 attempts for {agent_name}: {repr(e)}. Retrying next in chain...")
                            break
                        logger.warning(f"Provider {provider_name} failed for {agent_name}: {repr(e)}. Retrying attempt {attempt+1}...")
                        await asyncio.sleep(base_delay * (2 ** attempt) + random.uniform(0.1, 1.0))
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
                max_tokens=token_budget,
                response_format={"type": "json_object"} if provider_name == "nvidia" else None
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
                    
                    async with GLOBAL_LLM_SEMAPHORE:
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
                    is_429 = "429" in error_msg or "502" in error_msg or "503" in error_msg or "504" in error_msg
                    
                    if is_validation:
                        logger.error(f"Provider {provider_name} validation error for {agent_name}. Failing fast: {repr(e)}")
                        break  # No retries for validation error, fall back immediately
                        
                    if is_429:
                        if attempt >= 5:
                            logger.warning(f"Provider {provider_name} exhausted 429 retries for {agent_name}. Falling back.")
                            break
                        logger.warning(f"Provider {provider_name} rate limited for {agent_name}. Retrying...")
                    else:
                        if attempt >= 2:
                            logger.warning(f"Provider {provider_name} exhausted retries for {agent_name}. Falling back.")
                            break
                        logger.warning(f"Provider {provider_name} failed for {agent_name}: {repr(e)}. Retrying...")
                    
                    attempt += 1
                    await asyncio.sleep(base_delay * (2 ** attempt) + random.uniform(0.1, 1.0))
                    
        raise Exception(f"All providers exhausted for agent: {agent_name}. Routing failed.")
