"""Tracer"""
import time
class Tracer:
    def __init__(self): self.traces=[]
    async def trace(self, wid, tid, agent, action, **kw): self.traces.append({"workflow_id":wid,"task_id":tid,"agent":agent,"action":action,"timestamp":time.time()})
