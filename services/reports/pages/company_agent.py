from services.reports.pages.base import BasePageAgent
from services.reports.prompts.company import SYSTEM_PROMPT


class CompanyPageAgent(BasePageAgent):
    def __init__(self):
        super().__init__("router", SYSTEM_PROMPT)
