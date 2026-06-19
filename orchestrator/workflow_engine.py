"""Workflow Engine - Tracks step-by-step workflow progress"""
import time
from typing import Dict, List, Optional


class WorkflowEngine:
    def __init__(self):
        self.workflows: Dict[str, dict] = {}

    async def create(self, workflow_id: str, steps: List[dict]) -> dict:
        self.workflows[workflow_id] = {
            "steps": steps,
            "current": 0,
            "status": "running",
            "artifacts": [],
            "started_at": time.time(),
        }
        return self.workflows[workflow_id]

    async def next_step(self, workflow_id: str) -> Optional[dict]:
        wf = self.workflows.get(workflow_id)
        if not wf or wf["current"] >= len(wf["steps"]):
            return None
        step = wf["steps"][wf["current"]]
        wf["current"] += 1
        return step

    async def complete(self, workflow_id: str, artifact: dict):
        if workflow_id in self.workflows:
            wf = self.workflows[workflow_id]
            wf["artifacts"].append(artifact)
            if wf["current"] >= len(wf["steps"]):
                wf["status"] = "completed"
                wf["completed_at"] = time.time()

    async def fail(self, workflow_id: str, reason: str):
        if workflow_id in self.workflows:
            self.workflows[workflow_id]["status"] = "failed"
            self.workflows[workflow_id]["failure_reason"] = reason
            self.workflows[workflow_id]["failed_at"] = time.time()

    def get_status(self, workflow_id: str) -> Optional[dict]:
        return self.workflows.get(workflow_id)

    def get_progress(self, workflow_id: str) -> dict:
        wf = self.workflows.get(workflow_id)
        if not wf:
            return {"error": "not found"}
        total = len(wf["steps"])
        current = wf["current"]
        return {
            "workflow_id": workflow_id,
            "current_step": current,
            "total_steps": total,
            "percent": round((current / total) * 100) if total else 0,
            "status": wf["status"],
            "artifacts_count": len(wf["artifacts"]),
        }
