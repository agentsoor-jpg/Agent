"""
Dispatcher - Production-grade task & workflow coordinator.

Responsibilities:
  - Load routing policies from policies/routing-policy.json
  - Route tasks to correct agents based on type & complexity
  - Manage full workflow lifecycle (create, track, persist, complete)
  - File locking: one agent owns a file at a time
  - Fallback chain when an agent fails
  - Async throughout — never blocks
  - Persists state to state/ directory across restarts
  - SSE event broadcasting via orchestrator.sse_bus
"""

import asyncio
import json
import os
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from orchestrator.router import Router
from orchestrator.workflow_engine import WorkflowEngine
from orchestrator.state_manager import StateManager
from orchestrator.context_engine import ContextEngine
from orchestrator.policy_engine import PolicyEngine
from orchestrator.recovery_manager import RecoveryManager
from orchestrator.resource_engine import ResourceEngine
from orchestrator.scheduler import Scheduler
from orchestrator import sse_bus

from agents.openhands.adapter import OpenHandsAdapter
from agents.aider.adapter import AiderAdapter
from agents.bolt.adapter import BoltAdapter
from agents.replit.adapter import ReplitAdapter

STATE_DIR = Path("state")
STATE_FILE = STATE_DIR / "workflows.json"

# ── Agent ownership rules ─────────────────────────────────────
AGENT_CAPABILITIES = {
    "bolt": {
        "allowed_actions": {"scaffold", "generate", "prototype"},
        "can_create_files": True,
        "can_edit_existing": False,
        "max_concurrent": 1,
    },
    "aider": {
        "allowed_actions": {"edit", "refactor", "fix", "patch"},
        "can_create_files": False,
        "can_edit_existing": True,
        "max_concurrent": 2,
    },
    "openhands": {
        "allowed_actions": {"analyze", "diagnose", "review", "execute", "debug"},
        "can_create_files": True,
        "can_edit_existing": True,
        "max_concurrent": 1,
    },
    "replit": {
        "allowed_actions": {"test", "verify", "run", "preview"},
        "can_create_files": False,
        "can_edit_existing": False,
        "max_concurrent": 2,
    },
}

SIMPLE_TASK_KEYWORDS = {"fix", "rename", "typo", "comment", "format", "lint"}
COMPLEX_TASK_KEYWORDS = {"architecture", "refactor", "redesign", "migrate", "integrate", "review"}


class FileLock:
    """In-process file ownership tracker."""

    def __init__(self):
        self._locks: Dict[str, str] = {}

    def acquire(self, filepath: str, agent_id: str) -> bool:
        if filepath in self._locks and self._locks[filepath] != agent_id:
            return False
        self._locks[filepath] = agent_id
        return True

    def release(self, filepath: str, agent_id: str):
        if self._locks.get(filepath) == agent_id:
            del self._locks[filepath]

    def release_all(self, agent_id: str):
        to_remove = [k for k, v in self._locks.items() if v == agent_id]
        for k in to_remove:
            del self._locks[k]

    def get_owner(self, filepath: str) -> Optional[str]:
        return self._locks.get(filepath)

    def status(self) -> dict:
        return dict(self._locks)


class TaskQueue:
    """Priority task queue (non-blocking)."""

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()

    async def put(self, task: dict):
        await self._queue.put(task)

    async def get(self) -> dict:
        return await self._queue.get()

    def size(self) -> int:
        return self._queue.qsize()


class Dispatcher:
    def __init__(self):
        self.router = Router()
        self.workflow_engine = WorkflowEngine()
        self.state_manager = StateManager()
        self.context_engine = ContextEngine()
        self.policy_engine = PolicyEngine()
        self.recovery_manager = RecoveryManager()
        self.resource_engine = ResourceEngine()
        self.scheduler = Scheduler()

        self.agents: Dict[str, object] = {
            "openhands": OpenHandsAdapter(),
            "aider": AiderAdapter(),
            "bolt": BoltAdapter(),
            "replit": ReplitAdapter(),
        }

        self.active_workflows: Dict[str, dict] = {}
        self.file_lock = FileLock()
        self.task_queue = TaskQueue()
        self._agent_semaphores: Dict[str, asyncio.Semaphore] = {}

        self.workflow_policy = self._load_json("policies/workflow-policy.json", {"workflows": {}})
        self._restore_state()

        for agent_id, caps in AGENT_CAPABILITIES.items():
            self._agent_semaphores[agent_id] = asyncio.Semaphore(caps["max_concurrent"])

    # ── Policy loading ────────────────────────────────────────

    def _load_json(self, path: str, default: dict) -> dict:
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return default

    # ── State persistence ─────────────────────────────────────

    def _persist_state(self):
        try:
            STATE_DIR.mkdir(exist_ok=True)
            STATE_FILE.write_text(json.dumps(self.active_workflows, indent=2, default=str))
        except Exception:
            pass

    def _restore_state(self):
        try:
            if STATE_FILE.exists():
                data = json.loads(STATE_FILE.read_text())
                for wf in data.values():
                    if wf.get("status") == "running":
                        wf["status"] = "interrupted"
                self.active_workflows = data
        except Exception:
            self.active_workflows = {}

    # ── Complexity analysis ───────────────────────────────────

    def _estimate_complexity(self, requirements: str) -> str:
        text = requirements.lower()
        if any(k in text for k in COMPLEX_TASK_KEYWORDS):
            return "high"
        if any(k in text for k in SIMPLE_TASK_KEYWORDS):
            return "low"
        if len(text.split()) > 100:
            return "high"
        return "medium"

    def _smart_route(self, task_type: str, requirements: str) -> str:
        base_agent = self.router.route(task_type)
        complexity = self._estimate_complexity(requirements)
        if task_type == "file_editing" and complexity == "low":
            return "aider"
        if task_type in ("debugging", "code_review") or complexity == "high":
            return "openhands"
        if task_type == "app_scaffolding":
            return "bolt"
        if task_type == "code_execution":
            return "replit"
        return base_agent or "openhands"

    # ── Context window management ─────────────────────────────

    def _trim_context(self, context: dict, agent_id: str) -> dict:
        limits = {"openhands": 60000, "aider": 30000, "bolt": 20000, "replit": 10000}
        limit = limits.get(agent_id, 20000)
        ctx_str = json.dumps(context)
        if len(ctx_str) > limit:
            files = context.get("files", {})
            trimmed_files = {}
            total = 0
            for path, content in files.items():
                chars = len(content)
                if total + chars > limit // 2:
                    break
                trimmed_files[path] = content
                total += chars
            return {**context, "files": trimmed_files, "_trimmed": True}
        return context

    # ── SSE event helpers ─────────────────────────────────────

    def _emit(self, workflow_id: str, event_type: str, data: dict):
        """Publish an SSE event for this workflow."""
        sse_bus.publish(workflow_id, event_type, data)

    # ── Single step execution ─────────────────────────────────

    async def _execute_step(
        self,
        workflow_id: str,
        step: dict,
        payload: dict,
        step_index: int = 0,
        attempt: int = 0,
    ) -> dict:
        agent_id = step.get("agent")
        action = step.get("action")
        fallback_agent_id = step.get("fallback")
        max_retries = step.get("max_retries", 2)

        agent = self.agents.get(agent_id)
        if not agent:
            return {"status": "error", "error": f"Unknown agent: {agent_id}"}

        task = {
            "id": str(uuid.uuid4()),
            "action": action,
            "payload": payload,
            "workflow_id": workflow_id,
        }

        self._emit(workflow_id, "agent_started", {
            "agent": agent_id,
            "action": action,
            "step": step_index,
            "task_id": task["id"],
        })

        ctx = await self.context_engine.compile({}, [], {})
        ctx = self._trim_context(ctx, agent_id)

        semaphore = self._agent_semaphores.get(agent_id, asyncio.Semaphore(1))
        start_time = time.time()

        async with semaphore:
            try:
                result = await asyncio.wait_for(
                    agent.execute(task, ctx),
                    timeout=step.get("timeout", 300),
                )
            except asyncio.TimeoutError:
                result = {
                    "task_id": task["id"],
                    "agent_id": agent_id,
                    "status": "timeout",
                    "error": f"Step '{action}' exceeded {step.get('timeout', 300)}s timeout",
                    "modified_files": [],
                    "summary": "Timed out",
                    "artifacts": [],
                }
            except Exception as e:
                result = {
                    "task_id": task["id"],
                    "agent_id": agent_id,
                    "status": "error",
                    "error": str(e),
                    "modified_files": [],
                    "summary": f"Exception: {e}",
                    "artifacts": [],
                }

        duration = round(time.time() - start_time, 2)
        step_status = result.get("status", "error")

        event_type = "agent_completed" if step_status not in ("error", "timeout") else "agent_failed"
        self._emit(workflow_id, event_type, {
            "agent": agent_id,
            "action": action,
            "step": step_index,
            "status": step_status,
            "duration_s": duration,
            "files": len(result.get("modified_files", [])),
            "summary": result.get("summary", ""),
        })

        # Fallback chain
        if step_status in ("error", "timeout", "offline") and attempt < max_retries:
            recovery = await self.recovery_manager.handle_failure(agent_id, task["id"], result.get("error", ""))

            if recovery["action"] == "retry" and fallback_agent_id is None:
                self._emit(workflow_id, "step_progress", {"message": f"Retrying {agent_id} (attempt {attempt+2})", "step": step_index})
                await asyncio.sleep(2 ** attempt)
                return await self._execute_step(workflow_id, step, payload, step_index, attempt + 1)

            if recovery["action"] in ("retry", "fallback") and fallback_agent_id:
                self._emit(workflow_id, "step_progress", {"message": f"Falling back from {agent_id} to {fallback_agent_id}", "step": step_index})
                fallback_step = {**step, "agent": fallback_agent_id, "fallback": None}
                fallback_result = await self._execute_step(workflow_id, fallback_step, payload, step_index, 0)
                fallback_result["_fell_back_from"] = agent_id
                return fallback_result

        return result

    # ── Workflow lifecycle ────────────────────────────────────

    async def dispatch_workflow(self, workflow_type: str, payload: dict, plan: Optional[dict] = None) -> dict:
        workflow_id = str(uuid.uuid4())
        wf_config = self.workflow_policy.get("workflows", {}).get(workflow_type, {})
        steps: List[dict] = wf_config.get("steps", [])
        phases = wf_config.get("phases", ["execute"])

        record = {
            "id": workflow_id,
            "type": workflow_type,
            "status": "running",
            "payload": payload,
            "steps": steps,
            "phases": phases,
            "results": [],
            "plan": plan,
            "verification": None,
            "memory_stored": False,
            "created_at": time.time(),
            "updated_at": time.time(),
            "complexity": self._estimate_complexity(payload.get("requirements", "")),
        }
        self.active_workflows[workflow_id] = record
        self._persist_state()

        await self.workflow_engine.create(workflow_id, steps)

        # Emit workflow started
        self._emit(workflow_id, "workflow_started", {
            "workflow_id": workflow_id,
            "type": workflow_type,
            "phases": phases,
            "steps": len(steps),
            "complexity": record["complexity"],
        })

        results = []
        for i, step in enumerate(steps):
            self._emit(workflow_id, "step_progress", {
                "message": f"Phase {i+1}/{len(steps)}: {step['agent']} → {step['action']}",
                "step": i,
                "total": len(steps),
                "percent": round(i / len(steps) * 100),
            })

            result = await self._execute_step(workflow_id, step, payload, step_index=i)
            result["action"] = step.get("action")
            result["step_agent"] = step.get("agent")
            result["step_index"] = i
            results.append(result)

            await self.workflow_engine.complete(workflow_id, result)

            self.active_workflows[workflow_id]["results"] = results
            self.active_workflows[workflow_id]["updated_at"] = time.time()
            self._persist_state()

            if result.get("status") == "error" and wf_config.get("on_failure") == "stop":
                self.active_workflows[workflow_id]["status"] = "failed"
                self._persist_state()
                self._emit(workflow_id, "workflow_failed", {"error": result.get("error", "Step failed"), "step": i})
                sse_bus.close(workflow_id)
                return {
                    "success": False,
                    "workflow_id": workflow_id,
                    "workflow_type": workflow_type,
                    "steps_completed": len(results),
                    "results": results,
                    "error": result.get("error", "Step failed"),
                }

        self.active_workflows[workflow_id]["status"] = "completed"
        self.active_workflows[workflow_id]["updated_at"] = time.time()
        self._persist_state()

        self._emit(workflow_id, "workflow_completed", {
            "workflow_id": workflow_id,
            "steps_completed": len(results),
            "duration_s": round(time.time() - record["created_at"], 2),
        })
        sse_bus.close(workflow_id)

        return {
            "success": True,
            "workflow_id": workflow_id,
            "workflow_type": workflow_type,
            "steps_completed": len(results),
            "results": results,
        }

    async def get_workflow_status(self, workflow_id: str) -> Optional[dict]:
        return self.active_workflows.get(workflow_id)

    def get_all_workflows(self) -> list:
        return list(self.active_workflows.values())

    def update_workflow_field(self, workflow_id: str, key: str, value):
        if workflow_id in self.active_workflows:
            self.active_workflows[workflow_id][key] = value
            self.active_workflows[workflow_id]["updated_at"] = time.time()
            self._persist_state()

    # ── Task routing ──────────────────────────────────────────

    async def route_task(self, task_type: str, requirements: str = "") -> Optional[str]:
        return self._smart_route(task_type, requirements)

    async def get_fallback(self, agent_id: str) -> Optional[str]:
        return self.router.get_fallback(agent_id)

    # ── Agent health ──────────────────────────────────────────

    async def get_all_agent_status(self) -> dict:
        statuses = {}
        tasks = {
            agent_id: asyncio.create_task(agent.health_check())
            for agent_id, agent in self.agents.items()
        }
        await asyncio.gather(*tasks.values(), return_exceptions=True)
        for agent_id, agent in self.agents.items():
            statuses[agent_id] = agent.get_status()
        return statuses

    # ── File lock API ─────────────────────────────────────────

    def get_file_locks(self) -> dict:
        return self.file_lock.status()

    # ── Queue info ────────────────────────────────────────────

    def get_queue_size(self) -> int:
        return self.task_queue.size()
