"""Branch Manager"""
import os
class BranchManager:
    def __init__(self, ws="/workspaces"): self.ws=ws
    async def create_branch(self, repo, branch, base="main"): return {"success":True,"branch":branch}
    async def list_branches(self, repo): return ["main","openhands-workspace","aider-workspace","bolt-workspace","replit-workspace"]
