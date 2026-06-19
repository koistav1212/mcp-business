from services.research.base import BaseProvider
from typing import Dict, Any

class PeopleProvider(BaseProvider):
    """
    Simulates extracting key talent signals: executive leadership rosters, LinkedIn profiles,
    and active recruiting campaigns.
    """
    async def fetch(self, company: str) -> Dict[str, Any]:
        company_clean = company.lower().strip()
        
        if "zoho" in company_clean:
            return {
                "source_title": "LinkedIn Professional Network Directory",
                "source_url": "https://linkedin.com/company/zoho",
                "source_type": "professional_network",
                "leadership": [
                    {"name": "Sridhar Vembu", "role": "CEO & Founder", "linkedin_url": "https://linkedin.com/in/sridharvembu"},
                    {"name": "Radha Vembu", "role": "Product Leader", "linkedin_url": "https://linkedin.com/in/radhavembu"}
                ],
                "hiring_signals": [
                    {"role_title": "Senior React Developer", "department": "Engineering", "location": "Chennai, India"},
                    {"role_title": "AI Research Engineer", "department": "R&D", "location": "Austin, Texas"}
                ]
            }
        elif "google" in company_clean:
            return {
                "source_title": "Google Careers Portal",
                "source_url": "https://careers.google.com/jobs",
                "source_type": "careers_portal",
                "leadership": [
                    {"name": "Sundar Pichai", "role": "CEO", "linkedin_url": "https://linkedin.com/in/sundarpichai"},
                    {"name": "Demis Hassabis", "role": "CEO, Google DeepMind", "linkedin_url": "https://linkedin.com/in/demishassabis"}
                ],
                "hiring_signals": [
                    {"role_title": "Staff Software Engineer, Gemini", "department": "AI DeepMind", "location": "London, UK"}
                ]
            }
            
        return {
            "source_title": "Generic Job Bulletin",
            "source_url": f"https://jobsbulletin.com/{company_clean}",
            "source_type": "directory",
            "leadership": [],
            "hiring_signals": [
                {"role_title": "Customer Success Representative", "department": "Operations", "location": "Remote"}
            ]
        }
