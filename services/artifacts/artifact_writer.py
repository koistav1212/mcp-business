import json
import os
import logging
from typing import Any, Optional

logger = logging.getLogger("uvicorn.error")

class ArtifactWriter:
    """
    Lightweight utility class for writing debugging artifacts to the filesystem.
    Always overwrites existing files. No versioning, no replay.
    """
    ARTIFACTS_ROOT = "artifacts"

    @staticmethod
    def _default_encoder(obj: Any) -> Any:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        elif hasattr(obj, "dict"):
            return obj.dict()
        elif hasattr(obj, "__dict__"):
            return obj.__dict__
        elif isinstance(obj, set):
            return list(obj)
        return str(obj)

    @classmethod
    def write_json(cls, relative_path: str, data: Any):
        """
        Writes data to the artifacts directory as a JSON file.
        relative_path: e.g., 'agent_inputs/financial_agent.json'
        """
        try:
            filepath = os.path.join(cls.ARTIFACTS_ROOT, relative_path)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=cls._default_encoder)
        except Exception as e:
            logger.warning(f"ArtifactWriter: Failed to write JSON to {relative_path}: {e}")
            
    @classmethod
    def write_markdown(cls, relative_path: str, text: str):
        """
        Writes raw text to a markdown or text file.
        relative_path: e.g., 'synthesis/prompt.md'
        """
        try:
            filepath = os.path.join(cls.ARTIFACTS_ROOT, relative_path)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            logger.warning(f"ArtifactWriter: Failed to write MD to {relative_path}: {e}")

    @classmethod
    def write_validation_error(cls, directory: str, error_details: Any):
        """
        Saves a validation_error.json in the specific directory.
        directory: e.g., 'agent_outputs'
        """
        cls.write_json(f"{directory}/validation_error.json", error_details)
