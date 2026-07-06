from services.reports.pages.base import BasePageAgent
from services.reports.prompts.technology import SYSTEM_PROMPT


class TechnologyPageAgent(BasePageAgent):
    def __init__(self):
        super().__init__("technology_agent", SYSTEM_PROMPT)
