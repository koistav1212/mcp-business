import logging
from typing import Dict, List, Optional
from tools.base import BaseTool

logger = logging.getLogger(__name__)

class ToolRegistry:
    """
    Registry for tools. Tracks all active tool instances available to the executor.
    """
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a single tool instance."""
        if tool.name in self._tools:
            logger.warning(f"Overwriting already registered tool: {tool.name}")
        self._tools[tool.name] = tool
        logger.info(f"Registered tool in registry: {tool.name}")

    def get(self, name: str) -> Optional[BaseTool]:
        """Retrieve a tool by its unique name."""
        return self._tools.get(name)

    def list_tools(self) -> List[BaseTool]:
        """List all registered tool instances."""
        return list(self._tools.values())

    def list_tool_names(self) -> List[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

# Global singleton instance
tool_registry = ToolRegistry()
