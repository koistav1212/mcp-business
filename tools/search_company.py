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
        company_name = kwargs.get("company_name", "").lower()
        domain = kwargs.get("domain")

        # Mock database lookup
        mock_companies = {
            "zoho": {
                "name": "Zoho Corporation",
                "domain": "zoho.com",
                "industry": "Software / SaaS",
                "size": "10,000+ employees",
                "hq": "Chennai, India & Austin, Texas",
                "founded": 1996
            },
            "google": {
                "name": "Google LLC",
                "domain": "google.com",
                "industry": "Internet / Tech",
                "size": "150,000+ employees",
                "hq": "Mountain View, California",
                "founded": 1998
            }
        }

        # Simple string matching for simulation
        for key, details in mock_companies.items():
            if key in company_name or (domain and key in domain):
                return details

        return {
            "name": kwargs.get("company_name"),
            "domain": domain,
            "industry": "Unknown",
            "size": "Unknown",
            "hq": "Unknown",
            "founded": None,
            "note": "Company not found in direct database lookup."
        }
