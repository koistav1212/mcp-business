from services.reports.pages.base import BasePageAgent
from services.reports.prompts.competition import SYSTEM_PROMPT


class CompetitionPageAgent(BasePageAgent):
    def __init__(self):
        super().__init__("competitor_agent", SYSTEM_PROMPT)
