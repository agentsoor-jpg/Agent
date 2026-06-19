"""
وكيل المراقبة - خدمة مستقلة (Sidecar)
يراقب صحة الوكلاء ولا يؤثر على المنسق
"""
import asyncio
import time
from typing import Dict, List


class Watchdog:
    def __init__(self, event_bus=None):
        self.agents: Dict[str, dict] = {}
        self.event_bus = event_bus
        self.heartbeat_interval = 5  # ثواني
    
    def register_agent(self, agent_id: str, endpoint: str):
        """تسجيل وكيل للمراقبة"""
        self.agents[agent_id] = {
            "endpoint": endpoint,
            "last_heartbeat": time.time(),
            "status": "healthy",
            "restart_count": 0
        }
    
    async def monitor_loop(self):
        """حلقة المراقبة المستمرة"""
        while True:
            for agent_id, info in self.agents.items():
                is_alive = await self._check_health(info["endpoint"])
                
                if not is_alive:
                    info["status"] = "failing"
                    await self._handle_failure(agent_id)
                
                info["last_heartbeat"] = time.time()
            
            await asyncio.sleep(self.heartbeat_interval)
    
    async def _check_health(self, endpoint: str) -> bool:
        """فحص صحة وكيل"""
        try:
            # في الواقع: HTTP GET {endpoint}/health
            return True
        except:
            return False
    
    async def _handle_failure(self, agent_id: str):
        """معالجة فشل وكيل"""
        self.agents[agent_id]["restart_count"] += 1
        if self.event_bus:
            await self.event_bus.publish("agent:failed", {
                "agent_id": agent_id,
                "timestamp": time.time()
            })
    
    def get_status(self) -> dict:
        """تقرير حالة جميع الوكلاء"""
        return {
            agent_id: info["status"]
            for agent_id, info in self.agents.items()
        }
