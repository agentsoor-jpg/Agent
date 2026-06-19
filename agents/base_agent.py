"""Base Agent"""
from abc import ABC, abstractmethod
class BaseAgent(ABC):
    def __init__(self, agent_id, endpoint, capabilities):
        self.agent_id=agent_id; self.endpoint=endpoint; self.capabilities=capabilities; self.status="idle"
    @abstractmethod
    async def execute(self, task, context): pass
    async def health_check(self): return True
    def get_status(self): return {"agent_id":self.agent_id,"status":self.status}
