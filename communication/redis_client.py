"""Redis Client"""
import json
class RedisClient:
    def __init__(self, host="localhost", port=6379): self.host=host; self.port=port; self.store={}
    async def connect(self): return True
    async def publish(self, ch, msg): self.store[ch]=json.dumps(msg); return 1
