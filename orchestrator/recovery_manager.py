"""Recovery Manager - إدارة التعافي"""
import asyncio
from typing import Dict

class RecoveryManager:
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.failures: Dict[str, int] = {}
    async def handle_failure(self, agent_id: str, task_id: str, error: str) -> dict:
        self.failures[agent_id] = self.failures.get(agent_id, 0) + 1
        if self.failures[agent_id] <= self.max_retries:
            return {"action": "retry", "agent": agent_id, "attempt": self.failures[agent_id]}
        return {"action": "fallback", "agent": agent_id, "reason": "max_retries_exceeded"}
    async def reset(self, agent_id: str):
        self.failures[agent_id] = 0
    def get_failure_count(self, agent_id: str) -> int:
        return self.failures.get(agent_id, 0)
