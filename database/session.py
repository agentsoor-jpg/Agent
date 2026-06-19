"""Database Session"""
class DatabaseSession:
    def __init__(self, url="sqlite:///aios.db"): self.url=url; self.connected=False
    async def connect(self): self.connected=True
    async def disconnect(self): self.connected=False
