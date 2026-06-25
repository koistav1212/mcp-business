import asyncio
import logging
from services.registry.tool_registry import TOOLS
from services.research.compressor import ResearchMemory

logger = logging.getLogger("uvicorn.error")

class ToolRouterAgent:
    def __init__(self):
        self.memory = ResearchMemory()
        
    async def fetch(self, tool_name: str, target: str):
        if tool_name not in TOOLS:
            logger.warning(f"Tool {tool_name} not found in registry")
            return None
            
        cached_data = self.memory.get_cached_mcp(tool_name, target)
        if cached_data is not None:
            return cached_data
        
        tool_config = TOOLS[tool_name]
        logger.info(f"Routing to MCP Server: {tool_config['mcp_server']} | Cost: {tool_config['cost']}")
        
        instance = tool_config["instance"]
        data = await instance.fetch(target)
        self.memory.set_cached_mcp(tool_name, target, data)
        return data
        
    async def execute_batch(self, tool_requests: dict):
        """
        Takes a dict of {tool_name: target} and fetches them concurrently
        """
        tasks = []
        names = []
        for name, target in tool_requests.items():
            tasks.append(self.fetch(name, target))
            names.append(name)
            
        results = await asyncio.gather(*tasks)
        
        normalized_results = []
        for name, data in zip(names, results):
            if name == "market_data":
                normalized_results.append(self.normalize_market(data))
            elif name == "sec_data":
                normalized_results.append(self.normalize_sec(data))
            elif name == "news_feed":
                normalized_results.append(self.normalize_news(data))
            else:
                normalized_results.append(data)
                
        return dict(zip(names, normalized_results))

    def normalize_market(self, data):
        # Placeholder for actual Market MCP normalization
        if isinstance(data, dict) and not "normalized" in data:
            data["normalized"] = True
        return data

    def normalize_sec(self, data):
        # Placeholder for actual SEC MCP normalization
        if isinstance(data, dict) and not "normalized" in data:
            data["normalized"] = True
        return data

    def normalize_news(self, data):
        # Placeholder for actual News MCP normalization
        if isinstance(data, list):
            # Assuming it's already a list of news
            return data
        elif isinstance(data, dict) and "news" in data:
            return data["news"]
        return data

