"""Event Bus"""
import uuid, time
class EventBus:
    def __init__(self): self.subscribers={}; self.history=[]
    async def publish(self, etype, data, source="system"):
        ev={"event_id":str(uuid.uuid4()),"event_type":etype,"timestamp":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"source":source,"data":data}; self.history.append(ev); return ev
    def subscribe(self, etype, cb):
        if etype not in self.subscribers: self.subscribers[etype]=[]
        self.subscribers[etype].append(cb)
