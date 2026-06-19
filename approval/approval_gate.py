"""Approval Gate"""
from typing import Dict
import json, uuid
class ApprovalGate:
    def __init__(self): self.pending = {}
    async def check(self, action: str, ctx: dict) -> dict:
        if action in ["db_schema_changes","file_deletion","major_refactor"]:
            aid=str(uuid.uuid4()); self.pending[aid]={"action":action,"status":"pending"}; return {"approved":False,"approval_id":aid}
        return {"approved":True}
    async def approve(self, aid: str) -> dict:
        if aid in self.pending: self.pending[aid]["status"]="approved"; return {"approved":True}
        return {"approved":False}
