"""
جامع الإحصائيات - خدمة مستقلة
"""
import time
from typing import Dict, List


class MetricsCollector:
    def __init__(self):
        self.metrics: Dict[str, List[dict]] = {
            "task_durations": [],
            "agent_usage": {},
            "error_counts": {},
            "success_rate": 0.0
        }
    
    def record_task(self, agent_id: str, duration: float, success: bool):
        """تسجيل إحصائية مهمة"""
        self.metrics["task_durations"].append({
            "agent": agent_id,
            "duration": duration,
            "success": success,
            "timestamp": time.time()
        })
        
        if agent_id not in self.metrics["agent_usage"]:
            self.metrics["agent_usage"][agent_id] = 0
        self.metrics["agent_usage"][agent_id] += 1
    
    def record_error(self, agent_id: str, error: str):
        """تسجيل خطأ"""
        if agent_id not in self.metrics["error_counts"]:
            self.metrics["error_counts"][agent_id] = 0
        self.metrics["error_counts"][agent_id] += 1
    
    def get_report(self) -> dict:
        """تقرير إحصائي كامل"""
        return self.metrics
