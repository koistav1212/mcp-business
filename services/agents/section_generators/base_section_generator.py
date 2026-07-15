import json
import logging
from typing import Dict, Any, Type
import httpx
from services.llm.provider_router import ProviderRouter
from pydantic import BaseModel
from core.config import settings

logger = logging.getLogger("uvicorn.error")

class BaseSectionGenerator:
    """
    Base class for all specialized section generators.
    """
    def __init__(self, section_name: str, model_class: Type[BaseModel]):
        self.section_name = section_name
        self.model_class = model_class

    async def generate(self, context: Dict[str, Any], entity_name: str) -> BaseModel:
        # A smaller prompt tailored for a specific section improves Qwen-3.5-2B output
        system_instruction = (
            f"You are a specialized business analyst focusing on {self.section_name}. "
            f"Extract and generate structured intelligence for {entity_name} based on the provided data.\n"
            "Return ONLY a valid JSON object matching the requested schema exactly. Do not include markdown formatting or extra text."
        )

        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        prompt = f"Data:\n{json.dumps(context, default=str)[:8000]}" # Truncate for safety
        
        try:
            parsed = await ProviderRouter.generate_json(
                agent_name="section_generator",
                system_prompt=system_instruction,
                user_prompt=prompt
            )
            return self.model_class(**parsed)
        except Exception as e:
            logger.error(f"{self.__class__.__name__} failed: {e}")
            # Fallback to an empty model
            return self.model_class()
