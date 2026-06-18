import os
import shutil
from pathlib import Path
from core.config import settings

class LocalStorage:
    """
    Handles local file storage inside the project workspace under artifacts/
    and constructs public URLs for FastAPI to serve static files.
    """
    def __init__(self, base_dir: str = "artifacts", base_url: str = None):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        if base_url:
            self.base_url = base_url.rstrip("/")
        else:
            # Matches FastAPI static mount base URL
            self.base_url = f"http://{settings.API_HOST}:{settings.API_PORT}/static"

    def save_file(self, source_path: Path, file_type: str) -> str:
        """
        Copies a file from a temporary location to the artifacts subdirectory (e.g. pdf, ppt)
        and returns its publicly accessible download URL.
        """
        target_dir = self.base_dir / file_type
        target_dir.mkdir(parents=True, exist_ok=True)
        
        target_path = target_dir / source_path.name
        shutil.copy2(source_path, target_path)
        
        return f"{self.base_url}/{file_type}/{source_path.name}"

    def write_content(self, filename: str, content: bytes, file_type: str) -> str:
        """
        Writes raw binary content bytes to a file under the specified artifact subdirectory
        and returns its publicly accessible download URL.
        """
        target_dir = self.base_dir / file_type
        target_dir.mkdir(parents=True, exist_ok=True)
        
        target_path = target_dir / filename
        with open(target_path, "wb") as f:
            f.write(content)
            
        return f"{self.base_url}/{file_type}/{filename}"

# Global instance
local_storage = LocalStorage()
