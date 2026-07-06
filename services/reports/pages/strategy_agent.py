from services.reports.pages.base import BasePageAgent
from services.reports.prompts.strategy import SYSTEM_PROMPT


class StrategyPageAgent(BasePageAgent):
    def __init__(self):
        super().__init__("director", SYSTEM_PROMPT)
