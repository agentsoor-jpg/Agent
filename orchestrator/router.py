"""Router - Task routing with full fallback chain from policy"""
import json
from typing import Optional


class Router:
    def __init__(self, policy_path: str = "policies/routing-policy.json"):
        self.rules: dict = {}
        self.fallback_chain: dict = {}
        self._load(policy_path)

    def _load(self, path: str):
        try:
            with open(path) as f:
                data = json.load(f)
            self.rules = data.get("task_routing", {})
            self.fallback_chain = data.get("fallback_chain", {})
        except Exception:
            self.rules = {
                "app_scaffolding": "bolt",
                "ui_generation": "bolt",
                "file_editing": "aider",
                "refactoring": "aider",
                "bug_fixing": "aider",
                "code_execution": "replit",
                "testing": "replit",
                "verification": "replit",
                "autonomous_execution": "openhands",
                "debugging": "openhands",
                "code_review": "openhands",
                "analysis": "openhands",
            }
            self.fallback_chain = {
                "bolt": "aider",
                "aider": "openhands",
                "replit": "openhands",
                "openhands": None,
            }

    def route(self, task_type: str) -> Optional[str]:
        return self.rules.get(task_type)

    def get_fallback(self, agent_id: str) -> Optional[str]:
        return self.fallback_chain.get(agent_id)
