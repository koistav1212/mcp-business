import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger("uvicorn.error")

class ExecutionMonitor:
    """
    Tracks execution status, failures, and retries.
    """
    def __init__(self):
        self.completed_tasks = set()
        self.failed_tasks = set()
        self.retries = {}

    def mark_completed(self, task_id: str):
        self.completed_tasks.add(task_id)
        if task_id in self.failed_tasks:
            self.failed_tasks.remove(task_id)
        logger.info(f"Task {task_id} completed successfully.")

    def mark_failed(self, task_id: str) -> bool:
        """
        Returns True if the task can be retried, False if retry limit exceeded.
        """
        self.failed_tasks.add(task_id)
        current_retries = self.retries.get(task_id, 0)
        self.retries[task_id] = current_retries + 1
        
        logger.warning(f"Task {task_id} failed. Attempt {self.retries[task_id]}.")
        # Assuming a default max of 3 for now
        return self.retries[task_id] < 3
