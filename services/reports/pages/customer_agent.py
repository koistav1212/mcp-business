from services.reports.pages.base import BasePageAgent
from services.reports.prompts.customer import SYSTEM_PROMPT


class CustomerPageAgent(BasePageAgent):
    def __init__(self):
        super().__init__("news_agent", SYSTEM_PROMPT)
