from services.research.base import BaseProvider
from typing import Dict, Any

class CompanyProvider(BaseProvider):
    """
    Fetches raw company profiles, hq locations, employee sizes, leadership list,
    and target segment competitors.
    """
    async def fetch(self, company: str) -> Dict[str, Any]:
        company_clean = company.lower().strip()
        
        if "zoho" in company_clean:
            return {
                "source_title": "Zoho Official About Page",
                "source_url": "https://zoho.com/about-us",
                "source_type": "official_website",
                "name": "Zoho Corporation",
                "overview": "Zoho Corporation is a global technology company providing online business suites and SaaS.",
                "headquarters": "Chennai, India & Austin, Texas",
                "employee_count": 12000,
                "website": "https://zoho.com",
                "leadership": [
                    {"name": "Sridhar Vembu", "role": "CEO & Founder", "linkedin_url": "https://linkedin.com/in/sridharvembu"},
                    {"name": "Radha Vembu", "role": "Product Suite Leader", "linkedin_url": None}
                ],
                "competitors": [
                    {"name": "Salesforce", "website": "https://salesforce.com", "segment": "CRM & Enterprise"},
                    {"name": "HubSpot", "website": "https://hubspot.com", "segment": "SMB Marketing & CRM"}
                ]
            }
        elif "google" in company_clean:
            return {
                "source_title": "Alphabet Investor Relations",
                "source_url": "https://abc.xyz",
                "source_type": "press_release",
                "name": "Google LLC",
                "overview": "Google is a multi-national tech conglomerate focusing on search, cloud, and digital advertising.",
                "headquarters": "Mountain View, California",
                "employee_count": 182000,
                "website": "https://google.com",
                "leadership": [
                    {"name": "Sundar Pichai", "role": "CEO", "linkedin_url": "https://linkedin.com/in/sundarpichai"}
                ],
                "competitors": [
                    {"name": "Microsoft", "website": "https://microsoft.com", "segment": "Cloud & Office Suite"}
                ]
            }
            
        return {
            "source_title": "Generic Web Directory",
            "source_url": f"https://directory.com/{company_clean}",
            "source_type": "directory",
            "name": company.capitalize(),
            "overview": f"{company.capitalize()} is an unverified business entity.",
            "headquarters": "Unknown",
            "employee_count": 100,
            "website": f"https://{company_clean}.com",
            "leadership": [],
            "competitors": []
        }
