"""
إدارة الحالة - Redis + ChromaDB للذاكرة الطويلة
المنسق لا يحفظ الحالة، هذه الخدمة تفعلها
"""
from typing import Dict, Optional
import json
import time


class StateStore:
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.memory: Dict[str, dict] = {}  # محاكاة Redis
        self.long_term: list = []  # محاكاة ChromaDB
    
    async def save_state(self, workflow_id: str, state: dict):
        """حفظ حالة سير عمل"""
        self.memory[workflow_id] = {
            "state": state,
            "timestamp": time.time()
        }
    
    async def get_state(self, workflow_id: str) -> Optional[dict]:
        """استرجاع حالة سير عمل"""
        data = self.memory.get(workflow_id)
        return data["state"] if data else None
    
    async def save_memory(self, key: str, value: dict):
        """حفظ في الذاكرة الطويلة (ChromaDB)"""
        self.long_term.append({
            "key": key,
            "value": value,
            "timestamp": time.time()
        })
    
    async def search_memory(self, query: str) -> list:
        """بحث في الذاكرة الطويلة"""
        return [
            item for item in self.long_term
            if query.lower() in json.dumps(item).lower()
        ]
    
    async def get_all_states(self) -> dict:
        """كل الحالات النشطة"""
        return {
            wid: data["state"]
            for wid, data in self.memory.items()
        }
