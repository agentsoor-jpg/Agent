"""Recovery Manager - Exponential backoff, fallback chain"""
import time
from typing import Dict


class RecoveryManager:
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.failures: Dict[str, int] = {}
        self.last_failure: Dict[str, float] = {}

    async def handle_failure(self, agent_id: str, task_id: str, error: str) -> dict:
        self.failures[agent_id] = self.failures.get(agent_id, 0) + 1
        self.last_failure[agent_id] = time.time()
        attempt = self.failures[agent_id]

        if attempt <= self.max_retries:
            return {
                "action": "retry",
                "agent": agent_id,
                "attempt": attempt,
                "backoff_s": 2 ** (attempt - 1),
                "error": error,
            }
        return {
            "action": "fallback",
            "agent": agent_id,
            "attempt": attempt,
            "reason": "max_retries_exceeded",
            "error": error,
        }

    async def reset(self, agent_id: str):
        self.failures[agent_id] = 0

    def get_failure_count(self, agent_id: str) -> int:
        return self.failures.get(agent_id, 0)

    def get_status(self) -> dict:
        return {
            agent_id: {
                "failures": count,
                "last_failure": self.last_failure.get(agent_id),
            }
            for agent_id, count in self.failures.items()
        }
