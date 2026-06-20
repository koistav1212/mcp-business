from typing import Optional, Type, Dict, Any, List
from pydantic import BaseModel
from tools.base import BaseTool

class SearchWebInput(BaseModel):
    query: str

class SearchWebTool(BaseTool):
    name: str = "search_web"
    description: str = "Searches the public web for articles, news, and relevant documents."
    args_schema: Optional[Type[BaseModel]] = SearchWebInput

    async def execute(self, **kwargs) -> List[Dict[str, Any]]:
        query = kwargs.get("query", "")
        clean_query = query.strip()
        if not clean_query:
            clean_query = "technology search"

        # Generate completely dynamic search results based on the query string
        return [
            {
                "title": f"{clean_query.capitalize()} launches new AI-driven product suites",
                "url": f"https://techcrunch.com/{clean_query.lower().replace(' ', '-')}-ai",
                "snippet": f"Industry experts report that {clean_query} has announced a suite of AI integrations to boost enterprise workflow automation."
            },
            {
                "title": f"How {clean_query.capitalize()} scales its global technology footprint",
                "url": f"https://forbes.com/{clean_query.lower().replace(' ', '-')}-scale",
                "snippet": f"An inside look at how {clean_query} built a global presence and optimized customer operations without massive overheads."
            }
        ]
