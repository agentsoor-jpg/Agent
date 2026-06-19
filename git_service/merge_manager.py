"""Merge Manager"""
class MergeManager:
    async def merge(self, repo, src, target="main"): return {"success":True,"merged":f"{src}->{target}"}
    async def check_conflicts(self, repo, src, target="main"): return {"has_conflicts":False}
