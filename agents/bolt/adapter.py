"""Bolt Adapter - APP_GENERATION specialist
Responsibilities: scaffolding new projects, generating UI components from scratch.
NEVER edit existing files — only creates new structure.
"""
import os
import httpx
import time
from agents.base_agent import BaseAgent

TIMEOUT = 30.0


class BoltAdapter(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="bolt",
            endpoint=os.getenv("BOLT_URL") or os.getenv("BOLT_ENDPOINT", "http://bolt:3003"),
            capabilities=["APP_GENERATION", "UI_SCAFFOLDING", "PROTOTYPING"],
        )

    async def execute(self, task: dict, context: dict) -> dict:
        task_id = task.get("id", "unknown")
        action = task.get("action", "scaffold")
        payload = task.get("payload", {})

        self._set_busy(task)
        start = time.time()

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.post(
                    f"{self.endpoint}/generate",
                    json={
                        "task_id": task_id,
                        "action": action,
                        "requirements": payload.get("requirements", ""),
                        "stack": payload.get("stack", ""),
                        "features": payload.get("features", []),
                        "context": context,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                self._set_idle()
                return {
                    "task_id": task_id,
                    "agent_id": self.agent_id,
                    "status": "success",
                    "duration_s": round(time.time() - start, 2),
                    "modified_files": data.get("created_files", []),
                    "summary": data.get("summary", "Bolt scaffolded project"),
                    "next_actions": data.get("next_actions", []),
                    "artifacts": data.get("artifacts", []),
                    "workspace": data.get("workspace", ""),
                }
        except httpx.ConnectError:
            self._set_error()
            return self._offline_response(task_id, action, start, "Agent not reachable at port 3003")
        except httpx.TimeoutException:
            self._set_error()
            return self._offline_response(task_id, action, start, "Agent timed out after 30s")
        except httpx.HTTPStatusError as e:
            self._set_error()
            return self._offline_response(task_id, action, start, f"Agent returned HTTP {e.response.status_code}")
        except Exception as e:
            self._set_error()
            return self._offline_response(task_id, action, start, str(e))

    def _offline_response(self, task_id: str, action: str, start: float, reason: str) -> dict:
        return {
            "task_id": task_id,
            "agent_id": self.agent_id,
            "status": "offline",
            "duration_s": round(time.time() - start, 2),
            "modified_files": [],
            "summary": f"Bolt offline — {reason}. Action '{action}' queued for retry.",
            "next_actions": ["retry_when_available"],
            "error": reason,
            "artifacts": [],
            "workspace": "",
        }

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self.endpoint}/health")
                self.healthy = r.status_code < 500
        except Exception:
            self.healthy = False
        self.last_health_check = time.time()
        return self.healthy
