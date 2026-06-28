import os
import shutil
import logging

logger = logging.getLogger("uvicorn.error")

class ArtifactManager:
    """
    Manages the initialization and cleanup of the debugging artifacts workspace.
    Ensures that every request runs on a clean slate without session history.
    """
    ARTIFACTS_ROOT = "artifacts"
    
    REQUIRED_DIRS = [
        "provider_outputs",
        "evidence",
        "evidence_graph",
        "knowledge_views",
        "agent_inputs",
        "agent_outputs",
        "synthesis",
        "critic",
        "ui",
        "final"
    ]

    @classmethod
    def initialize_workspace(cls):
        """
        Wipes the existing artifacts directory and creates the required folder structure.
        Called at the beginning of each major API request.
        """
        try:
            # 1. Wipe existing
            if os.path.exists(cls.ARTIFACTS_ROOT):
                # Don't delete the root itself to prevent permission/mount issues,
                # just delete its contents.
                for item in os.listdir(cls.ARTIFACTS_ROOT):
                    item_path = os.path.join(cls.ARTIFACTS_ROOT, item)
                    if os.path.isfile(item_path):
                        os.unlink(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
            else:
                os.makedirs(cls.ARTIFACTS_ROOT, exist_ok=True)
                
            # 2. Recreate directory structure
            for d in cls.REQUIRED_DIRS:
                os.makedirs(os.path.join(cls.ARTIFACTS_ROOT, d), exist_ok=True)
                
            logger.info("ArtifactManager: Workspace initialized successfully.")
        except Exception as e:
            logger.warning(f"ArtifactManager: Failed to initialize workspace: {e}")
