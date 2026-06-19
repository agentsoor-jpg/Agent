"""State Manager - إدارة الحالة"""
from typing import Dict, Optional
import time

class StateManager:
    def __init__(self):
        self.states: Dict[str, dict] = {}
    async def save(self, key: str, state: dict):
        state["_timestamp"] = time.time()
        self.states[key] = state
    async def load(self, key: str) -> Optional[dict]:
        return self.states.get(key)
    async def delete(self, key: str):
        self.states.pop(key, None)
    async def exists(self, key: str) -> bool:
        return key in self.states
    def list_keys(self) -> list:
        return list(self.states.keys())
