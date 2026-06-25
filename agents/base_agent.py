"""Base Agent - Abstract contract all agents must implement"""
from abc import ABC, abstractmethod
from typing import Optional
import httpx
import time


class BaseAgent(ABC):
    def __init__(self, agent_id: str, endpoint: str, capabilities: list):
        self.agent_id = agent_id
        self.endpoint = endpoint
        self.capabilities = capabilities
        self.status = "idle"
        self.current_task: Optional[dict] = None
        self.task_count = 0
        self.error_count = 0
        self.last_health_check: Optional[float] = None
        self.healthy = False

    @abstractmethod
    async def execute(self, task: dict, context: dict) -> dict:
        pass

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self.endpoint}/health")
                self.healthy = r.status_code < 500
        except Exception:
            self.healthy = False
        self.last_health_check = time.time()
        return self.healthy

    def get_status(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "endpoint": self.endpoint,
            "capabilities": self.capabilities,
            "status": self.status,
            "healthy": self.healthy,
            "task_count": self.task_count,
            "error_count": self.error_count,
            "current_task": self.current_task.get("id") if self.current_task else None,
            "last_health_check": self.last_health_check,
        }

    def _set_busy(self, task: dict):
        self.status = "busy"
        self.current_task = task
        self.task_count += 1

    def _set_idle(self):
        self.status = "idle"
        self.current_task = None

    def _set_error(self):
        self.error_count += 1
        self.status = "idle"
        self.current_task = None
