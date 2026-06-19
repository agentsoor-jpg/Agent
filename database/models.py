"""Database Models"""
from datetime import datetime
class WorkflowModel:
    def __init__(self, wid, wtype): self.workflow_id=wid; self.workflow_type=wtype; self.status="pending"
class TaskModel:
    def __init__(self, tid, ttype, agent): self.task_id=tid; self.task_type=ttype; self.agent_id=agent; self.status="pending"
