from typing import Optional, Type
from pydantic import BaseModel
from tools.base import BaseTool
from connectors.gmail.actions import GmailConnector

class SendEmailInput(BaseModel):
    to: str
    subject: str
    body: str

class SendEmailTool(BaseTool):
    name: str = "send_email"
    description: str = "Sends a real-time email report or notice to target addresses."
    args_schema: Optional[Type[BaseModel]] = SendEmailInput

    async def execute(self, **kwargs) -> dict:
        to = kwargs["to"]
        subject = kwargs["subject"]
        body = kwargs["body"]

        # Fallback dynamic initialization if connector is not pre-registered
        if not self.connector:
            self.connector = GmailConnector()
            await self.connector.connect()

        # Execute connector-level action
        result = await self.connector.send_email(to, subject, body)
        return result
