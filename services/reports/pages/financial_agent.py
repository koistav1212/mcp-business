from services.reports.pages.base import BasePageAgent
from services.reports.prompts.financial import SYSTEM_PROMPT


class FinancialPageAgent(BasePageAgent):
    def __init__(self):
        super().__init__("financial_agent", SYSTEM_PROMPT)
