"""
خدمة الشفاء الذاتي - مستقلة تماماً
تقرأ السياسات من ملف خارجي ولا تغير كود المنسق
"""
import json
import time
from typing import Dict, Optional


class Healer:
    def __init__(self, policies_path: str = "policies/healing-policy.json"):
        self.policies = self._load_policies(policies_path)
        self.healing_history: list = []
    
    def _load_policies(self, path: str) -> dict:
        """تحميل سياسات الشفاء من ملف JSON"""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except:
            return self._default_policies()
    
    def _default_policies(self) -> dict:
        """سياسات افتراضية"""
        return {
            "max_restarts": 3,
            "restart_delay": 10,
            "fallback_agent": "openhands",
            "escalation_threshold": 5
        }
    
    async def handle_failure(self, agent_id: str, error: dict) -> dict:
        """معالجة فشل وكيل حسب السياسات"""
        max_restarts = self.policies.get("max_restarts", 3)
        
        self.healing_history.append({
            "agent_id": agent_id,
            "error": error,
            "timestamp": time.time()
        })
        
        recent_failures = len([
            h for h in self.healing_history
            if h["agent_id"] == agent_id
        ])
        
        if recent_failures < max_restarts:
            return {
                "action": "restart",
                "agent_id": agent_id,
                "attempt": recent_failures
            }
        else:
            fallback = self.policies.get("fallback_agent", "openhands")
            return {
                "action": "fallback",
                "agent_id": agent_id,
                "fallback_to": fallback,
                "reason": "exceeded_max_restarts"
            }
    
    async def heal(self, diagnosis: dict) -> dict:
        """تطبيق خطة الشفاء"""
        return await self.handle_failure(
            diagnosis.get("agent_id"),
            diagnosis.get("error")
        )
    
    def get_history(self) -> list:
        """سجل عمليات الشفاء"""
        return self.healing_history
