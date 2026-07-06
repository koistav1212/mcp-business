from services.reports.pages.base import BasePageAgent
from services.reports.prompts.risk import SYSTEM_PROMPT


class RiskPageAgent(BasePageAgent):
    def __init__(self):
        super().__init__("risk_agent", SYSTEM_PROMPT)
