"""Workflow Engine - محرك سير العمل"""
from typing import Dict, List, Optional

class WorkflowEngine:
    def __init__(self):
        self.workflows: Dict[str, dict] = {}
    async def create(self, workflow_id: str, steps: List[dict]) -> dict:
        self.workflows[workflow_id] = {"steps": steps, "current": 0, "status": "running", "artifacts": []}
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
            self.workflows[workflow_id]["artifacts"].append(artifact)
            if self.workflows[workflow_id]["current"] >= len(self.workflows[workflow_id]["steps"]):
                self.workflows[workflow_id]["status"] = "completed"
    def get_status(self, workflow_id: str) -> Optional[dict]:
        return self.workflows.get(workflow_id)
