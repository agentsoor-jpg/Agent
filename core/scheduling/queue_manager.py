"""
مدير طوابير المهام - خدمة مستقلة
يتحكم في أولوية المهام وتوزيعها
"""
from enum import Enum
from collections import deque
import asyncio


class TaskPriority(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class QueueManager:
    def __init__(self):
        self.queues = {
            TaskPriority.HIGH: deque(),
            TaskPriority.MEDIUM: deque(),
            TaskPriority.LOW: deque()
        }
        self.current_task = None
    
    async def enqueue(self, task: dict, priority: TaskPriority = TaskPriority.MEDIUM):
        """إضافة مهمة إلى الطابور"""
        self.queues[priority].append(task)
        return {"status": "queued", "task_id": task.get("id")}
    
    async def dequeue(self) -> dict:
        """سحب المهمة التالية حسب الأولوية"""
        for priority in [TaskPriority.HIGH, TaskPriority.MEDIUM, TaskPriority.LOW]:
            if self.queues[priority]:
                self.current_task = self.queues[priority].popleft()
                return self.current_task
        return None
    
    async def get_status(self) -> dict:
        """حالة الطوابير الحالية"""
        return {
            "high": len(self.queues[TaskPriority.HIGH]),
            "medium": len(self.queues[TaskPriority.MEDIUM]),
            "low": len(self.queues[TaskPriority.LOW]),
            "current": self.current_task
        }
