"""
Task management system.
"""

import time
import uuid
from typing import Dict, Any, Optional

from humblr.ai_client import AIClient


class TaskManager:
    def __init__(self, config: Dict[str, Any], storage, ai: AIClient):
        self.config = config
        self.storage = storage
        self.ai = ai

    def generate_dynamic_task(self, activity: Dict, corruption: float = None, memory: str = None) -> Optional[Dict]:
        if corruption is None:
            corruption = self.storage.get_corruption()
        if memory is None:
            memory = self.storage.get_memory_summary(5)
        task = self.ai.generate_dynamic_task(activity, corruption, memory)
        if task:
            task.setdefault("id", f"t_{uuid.uuid4().hex[:8]}")
            task.setdefault("created_at", time.time())
            task["completed"] = False
            self.storage.add_task_log(task)
            self.storage.add_memory("task_generated", task.get("title", "new task"), corruption)
            return task
        return None

    def add_task(self, task: Dict):
        self.storage.add_task_log(task)

    def get_active_tasks(self):
        return self.storage.get_active_tasks()

    def get_task(self, task_id: str) -> Optional[Dict]:
        for t in self.storage.task_log:
            if t.get("id") == task_id:
                return t
        return None

    def complete_task(self, task_id: str, proof_text: str = "", screenshot_path: str = None) -> bool:
        success = self.storage.mark_task_completed(task_id, proof_text, screenshot_path)
        if success:
            self.storage.increment("tasks_completed", 1)
        return success

    def get_task_summary(self) -> str:
        active = self.get_active_tasks()
        if not active:
            return "No active tasks. How disappointing."
        return "\n".join(f"- {t['title']}" for t in active[:5])
