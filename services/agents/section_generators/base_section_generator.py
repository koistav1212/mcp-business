import json
import logging
from typing import Dict, Any, Type
from pydantic import BaseModel, ValidationError
from services.llm.provider_router import ProviderRouter

logger = logging.getLogger("uvicorn.error")

class BaseSectionGenerator:
    """
    Base class for all specialized section generators.
    """
    def __init__(self, section_name: str, model_class: Type[BaseModel]):
        self.section_name = section_name
        self.model_class = model_class

    def build_context(self, slice_data: Dict[str, Any]) -> str:
        def deduplicate_and_truncate(data: Any) -> Any:
            if isinstance(data, list):
                seen = set()
                unique_list = []
                for item in data:
                    if isinstance(item, dict):
                        key = item.get("id") or item.get("url") or item.get("headline") or str(item)
                        if key not in seen:
                            seen.add(key)
                            unique_list.append({k: deduplicate_and_truncate(v) for k, v in item.items()})
                    else:
                        key = str(item)
                        if key not in seen:
                            seen.add(key)
                            unique_list.append(item)
                return unique_list[:10]
            elif isinstance(data, dict):
                return {k: deduplicate_and_truncate(v) for k, v in data.items()}
            return data
            
        slice_data = deduplicate_and_truncate(slice_data)
        return json.dumps(slice_data, default=str)

    def build_prompt(self, entity_name: str) -> str:
        def _simplify_schema(schema_dict: Dict[str, Any], indent: int = 0) -> str:
            lines = []
            prefix = " " * indent
            if "properties" in schema_dict:
                for k, v in schema_dict["properties"].items():
                    if "type" in v:
                        t = v["type"]
                        if t == "array":
                            items = v.get("items", {})
                            if items.get("type") == "object" and "properties" in items:
                                lines.append(f"{prefix}{k}: array of objects with:")
                                lines.append(_simplify_schema(items, indent + 4))
                            elif items.get("type"):
                                lines.append(f"{prefix}{k}: {items['type']}[]")
                            else:
                                lines.append(f"{prefix}{k}: array")
                        elif t == "object" and "properties" in v:
                            lines.append(f"{prefix}{k}: object with:")
                            lines.append(_simplify_schema(v, indent + 4))
                        else:
                            lines.append(f"{prefix}{k}: {t}")
                    elif "anyOf" in v:
                        lines.append(f"{prefix}{k}: any")
                    else:
                        lines.append(f"{prefix}{k}: any")
            return "\n".join(lines)

        raw_schema = self.model_class.model_json_schema()
        simplified_contract = _simplify_schema(raw_schema)

        system_instruction = f"""
You are a specialized business analyst focusing on {self.section_name}.
Extract and generate structured intelligence for {entity_name} based on the provided data.

Return JSON matching THIS SCHEMA EXACTLY.

{self.section_name} Output
{simplified_contract}

Rules:
- Never invent keys.
- Every required field must exist.
- Unknown values should be null or [].
- Return ONLY valid JSON.
- Do not output markdown.
"""
        return system_instruction

    def _validate_output(self, parsed: Any) -> BaseModel:
        if not isinstance(parsed, dict):
            raise ValueError("Parsed output is not a dictionary")
        return self.model_class.model_validate(parsed)

    async def _retry_on_validation_failure(self, system_prompt: str, user_prompt: str, error: Exception) -> BaseModel:
        retry_prompt = f"{system_prompt}\n\nYour previous response failed validation: {error}. Please fix and return ONLY valid JSON matching the schema exactly. Ensure all required fields are present."
        try:
            parsed = await ProviderRouter.generate_json(
                agent_name="section_generator",
                system_prompt=retry_prompt,
                user_prompt=user_prompt
            )
            return self._validate_output(parsed)
        except Exception as e:
            logger.error(f"{self.__class__.__name__} retry failed: {e}")
            return self.model_class()

    async def execute(self, slice_data: Dict[str, Any], entity_name: str) -> BaseModel:
        system_prompt = self.build_prompt(entity_name)
        context = self.build_context(slice_data)
        user_prompt = f"Data:\n{context}"
        
        logger.info(
            "SectionGenerator (%s) -> chars=%d",
            self.section_name,
            len(context)
        )

        try:
            parsed = await ProviderRouter.generate_json(
                agent_name="section_generator",
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            return self._validate_output(parsed)
        except (ValidationError, ValueError) as e:
            logger.warning(f"{self.__class__.__name__} validation failed: {e}. Retrying...")
            return await self._retry_on_validation_failure(system_prompt, user_prompt, e)
        except Exception as e:
            logger.error(f"{self.__class__.__name__} generation failed: {e}")
            return self.model_class()

    async def generate(self, slice_data: Dict[str, Any], entity_name: str) -> BaseModel:
        """
        Legacy generate method for backward compatibility, routes to execute().
        """
        return await self.execute(slice_data, entity_name)
