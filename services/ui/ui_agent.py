import json
import logging
from typing import Dict, Any, List
import httpx
from services.llm.provider_router import ProviderRouter
from core.config import settings

logger = logging.getLogger("uvicorn.error")

class UIAgent:
    """
    Takes the structured intelligence, narratives, and the UI plan, and generates
    the final semantic UI metadata for the frontend to render.
    NO BUSINESS REASONING happens here.
    """
    async def execute(self, query: str, context: Dict[str, Any], ui_plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        system_instruction = (
            "You are a UI Layout Engine. Your task is to map the provided data to UI components based on the ui_plan.\n"
            "Do NOT invent or infer any business facts. Only use the data provided.\n"
            "For each question in the ui_plan, define a widget object in a 'ui_generation' array.\n"
            "Each widget must have a 'ui' metadata object matching this schema:\n"
            "{'component': 'card', 'variant': 'primary', 'importance': 'critical', 'theme': 'blue', 'density': 'comfortable', "
            "'layout': {'width': 'full', 'height': 'dynamic', 'row_span': 2, 'col_span': 12}, "
            "'priority': 100, 'confidence': 1.0, 'collapsible': true, 'drill_down': false, 'loading_state': 'skeleton', 'exportable': true}\n"
            "Return a JSON object: {'ui_generation': [{'widget': '...', 'title': '...', 'data': {...}, 'ui': {...}}, ...]}"
        )

        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "ui_plan": ui_plan,
            "data": context # This includes sections and narratives
        }
        
        prompt = f"Map to UI Components:\n{json.dumps(payload, default=str)[:16000]}"
        
        try:
            parsed = await ProviderRouter.generate_json(
                agent_name="ui_agent",
                system_prompt=system_instruction,
                user_prompt=prompt
            )
                return parsed
        except Exception as e:
            logger.error(f"UIAgent failed: {e}")
            return {"ui_generation": []}
