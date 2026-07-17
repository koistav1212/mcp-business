import json
import logging
from typing import Dict, Any, Type
from services.llm.provider_router import ProviderRouter
from pydantic import BaseModel

logger = logging.getLogger("uvicorn.error")

class BaseSectionGenerator:
    """
    Base class for all specialized section generators.
    """
    def __init__(self, section_name: str, model_class: Type[BaseModel]):
        self.section_name = section_name
        self.model_class = model_class

    async def generate(self, slice_data: Dict[str, Any], entity_name: str) -> BaseModel:
        """
        Generates the structured section output by sending the strictly scoped slice data to the LLM.
        """
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
        prompt_payload = json.dumps(slice_data, default=str)
        prompt = f"Data:\n{prompt_payload}"

        logger.info(
            "SectionGenerator (%s) -> chars=%d",
            self.section_name,
            len(prompt_payload)
        )

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
