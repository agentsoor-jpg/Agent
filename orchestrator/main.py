"""
AI Engineering OS — Orchestrator API
FastAPI server. All endpoints are async. Never blocks.
Port is set by ORCHESTRATOR_PORT env var (default 8000).
"""

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from orchestrator.dispatcher import Dispatcher

# ── App ───────────────────────────────────────────────────────

app = FastAPI(
    title="AI Engineering OS",
    description="Hybrid AI Engineering Operating System",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

dispatcher = Dispatcher()

WORKSPACE_DIR = Path("workspaces")
WORKSPACE_DIR.mkdir(exist_ok=True)

STATIC_DIR = Path("static")
POLICIES_DIR = Path("policies")
ENV_FILE = Path(".env")

# ── Request models ────────────────────────────────────────────


class WorkflowRequest(BaseModel):
    requirements: str
    stack: Optional[str] = None
    features: Optional[List[str]] = None


class TaskRequest(BaseModel):
    type: str
    payload: dict
    requirements: Optional[str] = ""


class EnvUpdate(BaseModel):
    variables: Dict[str, str]


class PolicyUpdate(BaseModel):
    name: str
    content: dict


class CommandRequest(BaseModel):
    command: str
    cwd: Optional[str] = None


# ── Dashboard ─────────────────────────────────────────────────


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve the management dashboard."""
    html_file = STATIC_DIR / "index.html"
    if html_file.exists():
        return FileResponse(str(html_file))
    return HTMLResponse("<h1>Dashboard not found — place index.html in static/</h1>", status_code=404)


@app.get("/", include_in_schema=False)
async def root_redirect():
    return {
        "name": "AI Engineering OS",
        "version": "2.0.0",
        "dashboard": "/dashboard",
        "docs": "/docs",
        "agents": list(dispatcher.agents.keys()),
        "workflows": list(dispatcher.workflow_policy.get("workflows", {}).keys()),
        "endpoints": [
            "GET  /dashboard",
            "GET  /health",
            "GET  /agents/status",
            "POST /workflows/{type}",
            "GET  /workflows",
            "GET  /workflows/{id}/status",
            "POST /tasks/route",
            "GET  /env",
            "POST /env",
            "GET  /policies",
            "POST /policies",
            "GET  /files",
            "POST /files/upload",
            "POST /terminal",
        ],
    }


# ── Health ────────────────────────────────────────────────────


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "orchestrator",
        "version": "2.0.0",
        "timestamp": time.time(),
        "active_workflows": len(dispatcher.active_workflows),
        "queue_size": dispatcher.get_queue_size(),
        "file_locks": len(dispatcher.get_file_locks()),
    }


# ── Agents ────────────────────────────────────────────────────


@app.get("/agents/status")
async def agents_status():
    """Check health of all 4 agents (ports 3001-3004)."""
    statuses = await dispatcher.get_all_agent_status()
    return {
        "agents": statuses,
        "online_count": sum(1 for s in statuses.values() if s.get("healthy")),
        "total": len(statuses),
        "checked_at": time.time(),
    }


# ── Workflows ─────────────────────────────────────────────────


@app.post("/workflows/{workflow_type}")
async def execute_workflow(
    workflow_type: str,
    request: WorkflowRequest,
    background_tasks: BackgroundTasks,
):
    """Trigger a workflow. Runs synchronously and returns results."""
    valid = dispatcher.workflow_policy.get("workflows", {})
    if workflow_type not in valid:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown workflow '{workflow_type}'. Available: {list(valid.keys())}",
        )

    result = await dispatcher.dispatch_workflow(workflow_type, request.model_dump())

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Workflow failed"))

    return result


@app.get("/workflows/{workflow_id}/status")
async def get_workflow_status(workflow_id: str):
    status = await dispatcher.get_workflow_status(workflow_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    return status


@app.get("/workflows")
async def list_workflows():
    workflows = dispatcher.get_all_workflows()
    return {
        "active_workflows": workflows,
        "total": len(workflows),
        "by_status": {
            "running": sum(1 for w in workflows if w.get("status") == "running"),
            "completed": sum(1 for w in workflows if w.get("status") == "completed"),
            "failed": sum(1 for w in workflows if w.get("status") == "failed"),
            "interrupted": sum(1 for w in workflows if w.get("status") == "interrupted"),
        },
    }


# ── Task routing ──────────────────────────────────────────────


@app.post("/tasks/route")
async def route_task(request: TaskRequest):
    agent = await dispatcher.route_task(request.type, request.requirements or "")
    if not agent:
        raise HTTPException(status_code=404, detail=f"No agent for task type: {request.type}")
    return {
        "task_type": request.type,
        "assigned_agent": agent,
        "fallback": await dispatcher.get_fallback(agent),
        "complexity": dispatcher._estimate_complexity(request.requirements or ""),
    }


# ── Environment variables ─────────────────────────────────────


@app.get("/env")
async def read_env():
    """Read all variables from .env file."""
    result: Dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                result[key.strip()] = val.strip()
    return {"variables": result, "file": str(ENV_FILE)}


@app.post("/env")
async def write_env(update: EnvUpdate):
    """Write/update variables in .env file."""
    existing: Dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                existing[key.strip()] = val.strip()
    existing.update(update.variables)
    content = "\n".join(f"{k}={v}" for k, v in existing.items()) + "\n"
    ENV_FILE.write_text(content)
    return {"success": True, "variables_set": list(update.variables.keys()), "total": len(existing)}


# ── Policies ──────────────────────────────────────────────────


@app.get("/policies")
async def read_policies():
    """Read all policy JSON files."""
    results = {}
    if POLICIES_DIR.exists():
        for f in POLICIES_DIR.glob("*.json"):
            try:
                results[f.stem] = json.loads(f.read_text())
            except Exception:
                results[f.stem] = {"error": "invalid JSON"}
    return {"policies": results, "count": len(results)}


@app.post("/policies")
async def write_policy(update: PolicyUpdate):
    """Write/update a policy file."""
    POLICIES_DIR.mkdir(exist_ok=True)
    policy_file = POLICIES_DIR / f"{update.name}.json"
    policy_file.write_text(json.dumps(update.content, indent=2))
    # Reload workflow policy if that's what changed
    if update.name == "workflow-policy":
        dispatcher.workflow_policy = update.content
    return {"success": True, "file": str(policy_file)}


# ── File tree ─────────────────────────────────────────────────


@app.get("/files")
async def list_files(path: str = "workspaces"):
    """List files in the workspace directory."""
    base = Path(path)
    if not base.exists():
        return {"path": str(base), "entries": [], "error": "Path does not exist"}

    entries = []
    try:
        for item in sorted(base.rglob("*")):
            if item.name.startswith("."):
                continue
            entries.append({
                "path": str(item.relative_to(base)),
                "type": "file" if item.is_file() else "dir",
                "size": item.stat().st_size if item.is_file() else None,
                "modified": item.stat().st_mtime if item.is_file() else None,
            })
    except Exception as e:
        return {"path": str(base), "entries": [], "error": str(e)}

    return {"path": str(base), "entries": entries, "count": len(entries)}


@app.post("/files/upload")
async def upload_file(file: UploadFile = File(...), destination: str = "workspaces"):
    """Upload a file to the workspace."""
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / file.filename
    content = await file.read()
    target.write_bytes(content)
    return {
        "success": True,
        "filename": file.filename,
        "path": str(target),
        "size": len(content),
    }


# ── Terminal ──────────────────────────────────────────────────


@app.post("/terminal")
async def run_command(request: CommandRequest):
    """Run a shell command and return stdout/stderr (30s timeout)."""
    try:
        proc = await asyncio.create_subprocess_shell(
            request.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=request.cwd or str(Path.cwd()),
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        except asyncio.TimeoutError:
            proc.kill()
            return {
                "success": False,
                "stdout": "",
                "stderr": "Command timed out after 30 seconds",
                "exit_code": -1,
                "command": request.command,
            }

        return {
            "success": proc.returncode == 0,
            "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
            "exit_code": proc.returncode,
            "command": request.command,
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
            "command": request.command,
        }


# ── File locks ────────────────────────────────────────────────


@app.get("/locks")
async def get_locks():
    return {"locks": dispatcher.get_file_locks()}


# ── Entry point ───────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("ORCHESTRATOR_PORT", 8000))
    print(f"""
    ██████╗ AI Engineering OS v2.0
    ├── Orchestrator: FastAPI on port {port}
    ├── Dispatcher: Async with file locking
    ├── Agents: OpenHands (3001) | Aider (3002) | Bolt (3003) | Replit (3004)
    ├── Dashboard: http://localhost:{port}/dashboard
    └── Docs: http://localhost:{port}/docs
    """)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
