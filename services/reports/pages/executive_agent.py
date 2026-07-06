from services.reports.pages.base import BasePageAgent
from services.reports.prompts.executive import SYSTEM_PROMPT


class ExecutivePageAgent(BasePageAgent):
    def __init__(self):
        super().__init__("executive_qa", SYSTEM_PROMPT)
