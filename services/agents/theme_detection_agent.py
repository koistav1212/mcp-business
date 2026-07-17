import json
import logging
from typing import Dict, List
import httpx
from services.llm.provider_router import ProviderRouter
from services.schemas.insight import BusinessEvent
from core.config import settings

logger = logging.getLogger("uvicorn.error")

class ThemeDetectionAgent:
    """
    Takes clustered events and assigns business themes. Runs sequentially.
    """
    async def execute(self, clusters: Dict[str, List[BusinessEvent]]) -> Dict[str, str]:
        if not clusters:
            return {}

        # Prepare payload
        payload = {}
        for cluster_name, events in clusters.items():
            payload[cluster_name] = [e.headline for e in events]
            
        system_instruction = (
            "You are a strategic business analyst. Your task is to detect overarching business themes "
            "from the provided clusters of events. For each cluster, provide a 1-3 word business theme (e.g. 'AI Expansion', 'Cost Optimization').\n"
            "Respond in JSON format: {'themes': {'cluster_name': 'Detected Theme'}}."
        )

        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        prompt = f"Detect themes for these clusters:\n{json.dumps(payload)}"
        
        try:
            parsed = await ProviderRouter.generate_json(
                agent_name="theme_detector",
                system_prompt=system_instruction,
                user_prompt=prompt
            )
            if isinstance(parsed, dict):
                return parsed.get("themes", {})
            return {}
        except Exception as e:
            logger.error(f"ThemeDetectionAgent failed: {e}")
            return {}
