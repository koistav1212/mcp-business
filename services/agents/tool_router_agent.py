import logging
from typing import Any
from services.registry.tool_registry import TOOLS

logger = logging.getLogger("uvicorn.error")

class ToolRouterAgent:
    """
    Executes specific providers (tools).
    No planning, caching, or data merging occurs here.
    """
    
    async def fetch(self, tool_name: str, target: Any) -> Any:
        """
        Executes the provider's fetch method directly.
        Returns whatever ResearchEvidence[] the provider yields.
        """
        if tool_name not in TOOLS:
            logger.warning(f"Tool {tool_name} not found in registry")
            return None
            
        tool_config = TOOLS[tool_name]
        logger.info(f"Routing to Provider: {tool_name} | Cost: {tool_config.get('cost', 'unknown')}")
        
        instance = tool_config["instance"]
        
        # We rely on the provider returning List[ResearchEvidence]
        data = await instance.fetch(target)
        return data
