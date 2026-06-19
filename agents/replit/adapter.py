"""Replit Adapter - RUNTIME_EXECUTION specialist
Responsibilities: running commands, tests, verifying code, previewing apps.
NEVER generates or edits code — only executes.
"""
import httpx
import time
from agents.base_agent import BaseAgent

TIMEOUT = 30.0


class ReplitAdapter(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="replit",
            endpoint="http://localhost:3004",
            capabilities=["RUNTIME_EXECUTION", "TESTING", "VERIFICATION"],
        )

    async def execute(self, task: dict, context: dict) -> dict:
        task_id = task.get("id", "unknown")
        action = task.get("action", "run")
        payload = task.get("payload", {})

        self._set_busy(task)
        start = time.time()

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.post(
                    f"{self.endpoint}/run",
                    json={
                        "task_id": task_id,
                        "action": action,
                        "command": payload.get("command", ""),
                        "workspace": payload.get("workspace", ""),
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
                    "modified_files": [],
                    "summary": data.get("summary", "Replit executed command"),
                    "next_actions": data.get("next_actions", []),
                    "artifacts": data.get("artifacts", []),
                    "stdout": data.get("stdout", ""),
                    "stderr": data.get("stderr", ""),
                    "exit_code": data.get("exit_code", 0),
                    "tests_passed": data.get("tests_passed", None),
                }
        except httpx.ConnectError:
            self._set_error()
            return self._offline_response(task_id, action, start, "Agent not reachable at port 3004")
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
            "summary": f"Replit offline — {reason}. Action '{action}' queued for retry.",
            "next_actions": ["retry_when_available"],
            "error": reason,
            "artifacts": [],
            "stdout": "",
            "stderr": reason,
            "exit_code": -1,
            "tests_passed": None,
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
