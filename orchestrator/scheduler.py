"""Scheduler - جدولة المهام"""
from typing import Dict, List
import asyncio

class Scheduler:
    def __init__(self):
        self.tasks: Dict[str, dict] = {}
        self.running: List[str] = []
    async def schedule(self, task: dict, delay: float = 0) -> str:
        task_id = task.get("id", str(__import__("uuid").uuid4()))
        self.tasks[task_id] = task
        return task_id
    async def cancel(self, task_id: str) -> bool:
        if task_id in self.tasks:
            del self.tasks[task_id]
            return True
        return False
    def get_pending(self) -> list:
        return list(self.tasks.values())
