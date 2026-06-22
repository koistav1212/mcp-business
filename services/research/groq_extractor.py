import os
import httpx
import logging
from typing import Optional

logger = logging.getLogger("uvicorn.error")

async def extract_company_from_prompt_groq(prompt: str) -> Optional[str]:
    """
    Extracts the target company name from a user prompt using Groq API.
    This translates the TypeScript Groq example into a Python utility.
    """
    groq_api_key = os.environ.get("GROQ_API_KEY")
    groq_model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    
    if not groq_api_key:
        logger.warning("GROQ_API_KEY is not set. Skipping Groq company extraction.")
        return None
        
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {groq_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": groq_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a concise information extraction assistant. "
                                "Given a user's prompt, extract the target company name. "
                                "Return ONLY the company name as a raw string. "
                                "Do not include punctuation or extra text. "
                                "If no company name is found, return the exact word 'None'."
                            )
                        },
                        {
                            "role": "user",
                            "content": f"Extract the company name from this prompt: '{prompt}'"
                        }
                    ],
                    "temperature": 0.1,
                },
                timeout=15.0
            )
            
            if not response.is_success:
                logger.error(f"Groq API error: {response.status_code} {response.text}")
                return None
                
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            
            if not content or content.lower() == "none":
                return None
                
            return content
            
    except Exception as err:
        logger.error(f"Failed to call Groq for company extraction: {err}")
        return None
