"""Resource Engine - محرك الموارد"""
from typing import Dict

class ResourceEngine:
    def __init__(self):
        self.limits = {"openhands": {"memory": 2048, "cpu": 2}, "aider": {"memory": 1024, "cpu": 1}, "bolt": {"memory": 2048, "cpu": 2}, "replit": {"memory": 1024, "cpu": 1}}
        self.usage: Dict[str, dict] = {}
    async def allocate(self, agent_id: str) -> dict:
        limits = self.limits.get(agent_id, {"memory": 512, "cpu": 1})
        self.usage[agent_id] = {"allocated": limits, "status": "active"}
        return {"success": True, "agent": agent_id, "limits": limits}
    async def release(self, agent_id: str):
        self.usage.pop(agent_id, None)
    def get_usage(self) -> dict:
        return self.usage
