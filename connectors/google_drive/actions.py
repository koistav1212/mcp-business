import logging
from pathlib import Path
from typing import Any, Dict
from connectors.base import BaseConnector

logger = logging.getLogger(__name__)

class GoogleDriveConnector(BaseConnector):
    """
    Simulates Google Drive API file operations.
    Stores files in a local directory 'storage/google_drive' to represent Drive storage.
    """
    name: str = "google_drive"
    _connected: bool = False
    drive_root: Path = Path("storage/google_drive")

    async def connect(self) -> Any:
        logger.info("Initializing Google Drive client connection.")
        self.drive_root.mkdir(parents=True, exist_ok=True)
        self._connected = True
        return self

    async def close(self) -> None:
        logger.info("Closing Google Drive client connection.")
        self._connected = False

    async def upload_file(self, filename: str, content: bytes) -> Dict[str, Any]:
        """
        Uploads content bytes to Google Drive.
        Saves the file to 'storage/google_drive' and returns simulated Google Drive metadata.
        """
        if not self._connected:
            await self.connect()
            
        target_path = self.drive_root / filename
        with open(target_path, "wb") as f:
            f.write(content)
            
        # Create simulated ID and view link
        file_id = f"gdrive-mock-id-{filename.lower().replace(' ', '_')}"
        web_view_link = f"https://drive.google.com/file/d/{file_id}/view"
        
        logger.info(f"[GoogleDriveConnector] File uploaded: {filename} (ID: {file_id})")
        return {
            "file_id": file_id,
            "filename": filename,
            "web_view_link": web_view_link,
            "size_bytes": len(content)
        }
