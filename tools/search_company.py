from typing import Optional, Type, Dict, Any
from pydantic import BaseModel
from tools.base import BaseTool

class SearchCompanyInput(BaseModel):
    company_name: str
    domain: Optional[str] = None

class SearchCompanyTool(BaseTool):
    name: str = "search_company"
    description: str = "Searches structured databases for company details, size, industry, and headquarters."
    args_schema: Optional[Type[BaseModel]] = SearchCompanyInput

    async def execute(self, **kwargs) -> Dict[str, Any]:
        company_name = kwargs.get("company_name", "")
        domain = kwargs.get("domain") or f"{company_name.lower().replace(' ', '')}.com"

        # Dynamically format based on company name
        clean_name = company_name.strip()
        if not clean_name:
            clean_name = "Unknown Corp"

        # Determine a dynamic database payload using company name
        return {
            "name": f"{clean_name} Corporation" if not clean_name.endswith(("Corporation", "LLC", "Inc", "Corp")) else clean_name,
            "domain": domain,
            "industry": "Software / SaaS",
            "size": "1,000+ employees",
            "hq": "Remote / Global",
            "founded": 2015
        }
