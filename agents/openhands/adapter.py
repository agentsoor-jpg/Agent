"""OpenHands Adapter - AUTONOMOUS_EXECUTION specialist
Responsibilities: complex autonomous tasks, code review, full-codebase debugging.
NEVER use for simple file edits or scaffolding.
"""
import os
import httpx
import time
from typing import Optional
from agents.base_agent import BaseAgent

TIMEOUT = 30.0


class OpenHandsAdapter(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="openhands",
            endpoint=os.getenv("OPENHANDS_URL") or os.getenv("OPENHANDS_ENDPOINT", "http://openhands:3001"),
            capabilities=["AUTONOMOUS_EXECUTION", "CODE_REVIEW", "DEBUGGING"],
        )

    async def execute(self, task: dict, context: dict) -> dict:
        task_id = task.get("id", "unknown")
        action = task.get("action", "execute")
        payload = task.get("payload", {})

        self._set_busy(task)
        start = time.time()

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.post(
                    f"{self.endpoint}/execute",
                    json={
                        "task_id": task_id,
                        "action": action,
                        "payload": payload,
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
                    "modified_files": data.get("modified_files", []),
                    "summary": data.get("summary", "OpenHands completed task"),
                    "next_actions": data.get("next_actions", []),
                    "artifacts": data.get("artifacts", []),
                }
        except httpx.ConnectError:
            self._set_error()
            return self._offline_response(task_id, action, start, "Agent not reachable at port 3001")
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
            "summary": f"OpenHands offline — {reason}. Action '{action}' queued for retry.",
            "next_actions": ["retry_when_available"],
            "error": reason,
            "artifacts": [],
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
