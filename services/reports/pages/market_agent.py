from services.reports.pages.base import BasePageAgent
from services.reports.prompts.market import SYSTEM_PROMPT


class MarketPageAgent(BasePageAgent):
    def __init__(self):
        super().__init__("industry_agent", SYSTEM_PROMPT)
