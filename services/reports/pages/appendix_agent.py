from services.reports.pages.base import BasePageAgent
from services.reports.prompts.appendix import SYSTEM_PROMPT


class AppendixPageAgent(BasePageAgent):
    def __init__(self):
        super().__init__("router", SYSTEM_PROMPT)
