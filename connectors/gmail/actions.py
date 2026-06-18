import logging
from typing import Any, List, Dict, ClassVar
from connectors.base import BaseConnector

logger = logging.getLogger(__name__)

class GmailConnector(BaseConnector):
    """
    Simulates a Gmail client connection. Traces sent emails in an in-memory outbox list.
    """
    name: str = "gmail"
    _connected: bool = False
    _outbox: ClassVar[List[Dict[str, Any]]] = []

    async def connect(self) -> Any:
        logger.info("Connecting to Gmail API using OAuth credentials.")
        self._connected = True
        return self

    async def close(self) -> None:
        logger.info("Closing Gmail connection session.")
        self._connected = False

    async def send_email(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        """
        Sends an email. Under the hood, this simulates the SMTP/API request,
        adds a receipt to the outbox, and logs the action.
        """
        if not self._connected:
            await self.connect()
            
        email_record = {
            "to": to,
            "subject": subject,
            "body": body,
            "status": "sent"
        }
        self._outbox.append(email_record)
        logger.info(f"[GmailConnector] Sent email successfully to {to}. Subject: {subject}")
        return email_record

    def get_outbox(self) -> List[Dict[str, Any]]:
        """Retrieve sent emails for audit/testing."""
        return self._outbox
