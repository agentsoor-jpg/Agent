"""Docker Manager"""
class DockerManager:
    def __init__(self): self.containers={}
    async def create_sandbox(self, agent_id): return {"success":True,"container_id":f"sandbox-{agent_id}"}
