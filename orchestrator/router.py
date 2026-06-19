"""Router - توجيه المهام"""
import json
from typing import Optional

class Router:
    def __init__(self, policy_path: str = "policies/routing-policy.json"):
        self.rules = {}
        try:
            with open(policy_path) as f:
                self.rules = json.load(f).get("task_routing", {})
        except:
            self.rules = {"app_scaffolding": "bolt", "file_editing": "aider", "code_execution": "replit", "code_generation": "openhands", "debugging": "openhands", "code_review": "openhands"}
    def route(self, task_type: str) -> Optional[str]:
        return self.rules.get(task_type)
    def get_fallback(self, agent_id: str) -> Optional[str]:
        chain = {"bolt": "aider", "aider": "openhands", "replit": "openhands"}
        return chain.get(agent_id)
