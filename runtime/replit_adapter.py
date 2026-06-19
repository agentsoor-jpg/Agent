"""Replit Runtime"""
import subprocess
class ReplitRuntime:
    def __init__(self, ws="/workspaces"): self.ws=ws
    async def execute(self, cmd: str, cwd=None) -> dict:
        try:
            r=subprocess.run(cmd,shell=True,cwd=cwd or self.ws,capture_output=True,text=True,timeout=300)
            return {"success":r.returncode==0,"stdout":r.stdout,"stderr":r.stderr}
        except Exception as e: return {"success":False,"error":str(e)}
