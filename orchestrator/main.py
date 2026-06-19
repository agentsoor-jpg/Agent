"""
AI Engineering OS — Orchestrator API v3.0
FastAPI server. All endpoints are async. Never blocks.
Port is set by ORCHESTRATOR_PORT env var (default 8000).

v3.0 additions:
  - SSE streaming: GET /stream/workflows/{id}
  - 5-phase execution protocol (context→plan→execute→verify→learn)
  - Permanent memory: GET/POST /memory/projects
  - Pre-planning: POST /plan/generate
  - Verification results: GET /verify/{workflow_id}
"""

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

# Allow running as `python orchestrator/main.py` (adds workspace root to path)
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

# Load .env file if present (no-op in production if file is absent)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

# ── API keys (read from env; None-safe — never crash on missing keys) ─────────
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY     = os.getenv("GOOGLE_API_KEY")
DEEPSEEK_API_KEY   = os.getenv("DEEPSEEK_API_KEY")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY")

# ── Runtime config ─────────────────────────────────────────────────────────────
REDIS_URL    = os.getenv("REDIS_URL",    "redis://localhost:6379")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///aios.db")
APP_ENV      = os.getenv("APP_ENV",      "development")
LOG_LEVEL    = os.getenv("LOG_LEVEL",    "INFO")

from orchestrator.dispatcher import Dispatcher
from orchestrator import sse_bus

# New v3 modules
from memory.vector_store import (
    store_project, search_similar, get_project_context,
    update_project, list_all_projects, load_context_for_workflow,
    update_user_preferences,
)
from memory.project_context import create_context, drop_context, get_context
from planning.plan_generator import generate_plan
from planning.dependency_resolver import resolve_order
from verification.build_verifier import verify_build
from verification.completeness_checker import check_completeness
from evaluation.validator import validate_agent_output, validate_file_content
from evaluation.consistency_checker import check_consistency

# ── App ───────────────────────────────────────────────────────

app = FastAPI(
    title="AI Engineering OS",
    description="Hybrid AI Engineering Operating System — v3.0 with permanent memory, SSE streaming, and 5-phase protocol",
    version="3.0.0",
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

# In-memory verification results store
_verification_results: Dict[str, dict] = {}


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


class PlanRequest(BaseModel):
    requirements: str
    stack: Optional[str] = None
    features: Optional[List[str]] = None


class MemoryProjectRequest(BaseModel):
    name: str
    description: str
    architecture: Optional[str] = ""
    decisions: Optional[List[str]] = []
    patterns: Optional[List[str]] = []
    stack: Optional[List[str]] = []
    files: Optional[dict] = {}


class PreferencesRequest(BaseModel):
    preferences: dict


# ── Dashboard ─────────────────────────────────────────────────

@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard():
    html_file = STATIC_DIR / "index.html"
    if html_file.exists():
        return FileResponse(str(html_file))
    return HTMLResponse("<h1>Dashboard not found — place index.html in static/</h1>", status_code=404)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": "AI Engineering OS",
        "version": "3.0.0",
        "dashboard": "/dashboard",
        "docs": "/docs",
        "agents": list(dispatcher.agents.keys()),
        "workflows": list(dispatcher.workflow_policy.get("workflows", {}).keys()),
        "endpoints": [
            "GET  /dashboard", "GET  /health", "GET  /agents/status",
            "POST /workflows/{type}", "GET  /workflows", "GET  /workflows/{id}/status",
            "GET  /stream/workflows/{id}",
            "POST /tasks/route",
            "GET  /env", "POST /env",
            "GET  /policies", "POST /policies",
            "GET  /files", "POST /files/upload",
            "POST /terminal", "GET  /locks",
            "GET  /memory/projects", "POST /memory/projects",
            "GET  /memory/projects/{id}", "POST /memory/search",
            "POST /plan/generate",
            "GET  /verify/{workflow_id}",
        ],
    }


# ── Health ────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "orchestrator",
        "version": "3.0.0",
        "timestamp": time.time(),
        "active_workflows": len(dispatcher.active_workflows),
        "queue_size": dispatcher.get_queue_size(),
        "file_locks": len(dispatcher.get_file_locks()),
        "memory_projects": len(list_all_projects()),
    }


# ── Agents ────────────────────────────────────────────────────

@app.get("/agents/status")
async def agents_status():
    statuses = await dispatcher.get_all_agent_status()
    return {
        "agents": statuses,
        "online_count": sum(1 for s in statuses.values() if s.get("healthy")),
        "total": len(statuses),
        "checked_at": time.time(),
    }


# ── SSE Streaming ─────────────────────────────────────────────

@app.get("/stream/workflows/{workflow_id}", include_in_schema=False)
async def stream_workflow(workflow_id: str):
    """
    SSE endpoint — subscribe to real-time events for a workflow.
    Events: workflow_started, agent_started, agent_completed, agent_failed,
            step_progress, workflow_completed, workflow_failed
    """
    queue = sse_bus.subscribe(workflow_id)

    async def event_generator() -> AsyncGenerator[str, None]:
        # Send connection confirmation
        yield sse_bus.format_sse({"event": "connected", "workflow_id": workflow_id, "timestamp": time.time(), "data": {}})
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25.0)
                    if event is None:
                        yield sse_bus.format_sse({"event": "stream_closed", "workflow_id": workflow_id, "timestamp": time.time(), "data": {}})
                        break
                    yield sse_bus.format_sse(event)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            sse_bus.unsubscribe(workflow_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Workflows — 5-phase protocol ──────────────────────────────

@app.post("/workflows/{workflow_type}")
async def execute_workflow(workflow_type: str, request: WorkflowRequest, background_tasks: BackgroundTasks):
    """
    Execute a workflow using the 5-phase protocol:
      Phase 0 — CONTEXT: Load past projects from memory, find similar patterns
      Phase 1 — PLAN: Generate architecture plan, resolve dependencies
      Phase 2 — EXECUTE: Run agents step by step with SSE streaming
      Phase 3 — VERIFY: Validate outputs, run build checks
      Phase 4 — LEARN: Store everything in permanent memory
    """
    valid = dispatcher.workflow_policy.get("workflows", {})
    if workflow_type not in valid:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown workflow '{workflow_type}'. Available: {list(valid.keys())}",
        )

    payload = request.model_dump()
    requirements = request.requirements

    # ── Phase 0: CONTEXT ─────────────────────────────────────
    memory_context = load_context_for_workflow(requirements)
    payload["_memory_context"] = memory_context

    # Create project context tracker
    workflow_id_placeholder = str(uuid.uuid4())
    proj_ctx = create_context(workflow_id_placeholder, requirements)

    # ── Phase 1: PLAN ─────────────────────────────────────────
    plan = generate_plan(requirements, stack=request.stack, features=request.features)
    resolved = resolve_order(plan["phases"])
    plan["resolved_order"] = resolved
    payload["_plan"] = plan

    # ── Phase 2: EXECUTE ──────────────────────────────────────
    result = await dispatcher.dispatch_workflow(workflow_type, payload, plan=plan)
    workflow_id = result["workflow_id"]

    # Update context tracker with actual workflow_id
    drop_context(workflow_id_placeholder)

    # ── Phase 3: VERIFY ───────────────────────────────────────
    build_result = await verify_build("workspaces")
    completeness = check_completeness(requirements, workspace_path="workspaces")

    # Validate each agent output
    validation_results = []
    for step_result in result.get("results", []):
        vr = validate_agent_output(step_result, step_result.get("action", "unknown"))
        validation_results.append({
            "step": step_result.get("action"),
            "agent": step_result.get("agent_id"),
            "valid": vr["valid"],
            "errors": vr["errors"],
            "warnings": vr["warnings"],
        })

    verification = {
        "workflow_id": workflow_id,
        "build": build_result,
        "completeness": completeness,
        "validation": validation_results,
        "overall_passed": build_result["passed"] and completeness["percentage"] >= 50,
        "verified_at": time.time(),
    }
    _verification_results[workflow_id] = verification
    dispatcher.update_workflow_field(workflow_id, "verification", verification)

    # ── Phase 4: LEARN ────────────────────────────────────────
    project_id = store_project({
        "name": f"Workflow: {workflow_type}",
        "description": requirements,
        "architecture": json.dumps(plan.get("component_tree", {})),
        "decisions": [s.get("summary", "") for s in result.get("results", []) if s.get("summary")],
        "patterns": plan.get("detected_stack", []) + plan.get("detected_features", []),
        "stack": plan.get("detected_stack", []),
        "workflow_id": workflow_id,
        "complexity": plan.get("complexity", "medium"),
    })
    dispatcher.update_workflow_field(workflow_id, "memory_stored", True)
    dispatcher.update_workflow_field(workflow_id, "project_id", project_id)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Workflow failed"))

    return {
        **result,
        "plan": plan,
        "verification": verification,
        "project_id": project_id,
        "phases_completed": ["context", "plan", "execute", "verify", "learn"],
    }


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


# ── Pre-execution planning ────────────────────────────────────

@app.post("/plan/generate")
async def generate_plan_endpoint(request: PlanRequest):
    """Generate a detailed architecture plan without executing."""
    plan = generate_plan(request.requirements, stack=request.stack, features=request.features)
    resolved = resolve_order(plan["phases"])
    return {
        "plan": plan,
        "resolved_order": resolved,
        "summary": {
            "complexity": plan["complexity"],
            "phases": plan["total_phases"],
            "agents": plan["agents_involved"],
            "stack": plan["detected_stack"],
            "features": plan["detected_features"],
            "estimated_files": f"{plan['estimates']['files_min']}–{plan['estimates']['files_max']}",
            "estimated_hours": plan["estimates"]["estimated_hours"],
        },
    }


# ── Verification ──────────────────────────────────────────────

@app.get("/verify/{workflow_id}")
async def get_verification(workflow_id: str):
    """Get verification results for a completed workflow."""
    result = _verification_results.get(workflow_id)
    if not result:
        # Run live verification
        build = await verify_build("workspaces")
        wf = dispatcher.active_workflows.get(workflow_id, {})
        completeness = check_completeness(
            wf.get("payload", {}).get("requirements", ""),
            workspace_path="workspaces",
        )
        result = {
            "workflow_id": workflow_id,
            "build": build,
            "completeness": completeness,
            "validation": [],
            "overall_passed": build["passed"],
            "verified_at": time.time(),
        }
    return result


# ── Memory ────────────────────────────────────────────────────

@app.get("/memory/projects")
async def list_memory_projects():
    """List all projects stored in permanent memory."""
    projects = list_all_projects()
    return {
        "projects": projects,
        "total": len(projects),
    }


@app.post("/memory/projects")
async def save_memory_project(request: MemoryProjectRequest):
    """Manually save a project to permanent memory."""
    project_id = store_project(request.model_dump())
    return {"success": True, "project_id": project_id}


@app.get("/memory/projects/{project_id}")
async def get_memory_project(project_id: str):
    """Get full details of a stored project."""
    project = get_project_context(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found in memory")
    return project


@app.post("/memory/search")
async def search_memory(request: PlanRequest):
    """Search past projects by similarity to requirements."""
    results = search_similar(request.requirements, top_k=5)
    return {"results": results, "query": request.requirements, "total": len(results)}


@app.post("/memory/preferences")
async def set_preferences(request: PreferencesRequest):
    updated = update_user_preferences(request.preferences)
    return {"success": True, "preferences": updated}


# ── Environment variables ─────────────────────────────────────

@app.get("/env")
async def read_env():
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
    POLICIES_DIR.mkdir(exist_ok=True)
    policy_file = POLICIES_DIR / f"{update.name}.json"
    policy_file.write_text(json.dumps(update.content, indent=2))
    if update.name == "workflow-policy":
        dispatcher.workflow_policy = update.content
    return {"success": True, "file": str(policy_file)}


# ── File tree ─────────────────────────────────────────────────

@app.get("/files")
async def list_files(path: str = "workspaces"):
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
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / file.filename
    content = await file.read()
    target.write_bytes(content)
    return {"success": True, "filename": file.filename, "path": str(target), "size": len(content)}


# ── Terminal ──────────────────────────────────────────────────

@app.post("/terminal")
async def run_command(request: CommandRequest):
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
            return {"success": False, "stdout": "", "stderr": "Timed out after 30s", "exit_code": -1, "command": request.command}
        return {
            "success": proc.returncode == 0,
            "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
            "exit_code": proc.returncode,
            "command": request.command,
        }
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "exit_code": -1, "command": request.command}


# ── File locks ────────────────────────────────────────────────

@app.get("/locks")
async def get_locks():
    return {"locks": dispatcher.get_file_locks()}


# ── v7.0 API Endpoints ─────────────────────────────────────────

# Import new v7.0 modules (optional - graceful degradation)
try:
    from core.security import (
        SecurityHeaders, RateLimiter, APIKeyManager,
        general_rate_limiter, api_key_manager, input_sanitizer,
    )
    from core.reliability import (
        health_check_manager, graceful_shutdown, CircuitBreaker,
    )
    from core.monitoring import (
        metrics_collector, prometheus_exporter, health_dashboard,
        alert_manager, performance_monitor, uptime_tracker,
    )
    from integrations.webhook_manager import webhook_manager
    from integrations.api_gateway import APIGateway, api_gateway
    from coordination.task_orchestrator import task_orchestrator
    from coordination.quality_controller import quality_controller
    from coordination.conflict_resolver import conflict_resolver
    from memory.context_window_manager import context_manager
    from memory.forgetting_curve import forgetting_curve
    
    V70_MODULES_LOADED = True
except ImportError as e:
    print(f"v7.0 modules not fully available: {e}")
    V70_MODULES_LOADED = False


# ── v7.0 Endpoints ───────────────────────────────────────────

@app.get("/api/v1/health")
async def api_health():
    """v7 API health check."""
    uptime_data = {}
    if V70_MODULES_LOADED:
        try:
            uptime_data = uptime_tracker.get_uptime_stats()
        except Exception:
            uptime_data = {}
    return {
        "status": "healthy",
        "version": "7.0.0",
        "uptime": uptime_data,
    }


@app.get("/api/v1/metrics")
async def api_metrics():
    """Prometheus metrics endpoint."""
    if not V70_MODULES_LOADED:
        raise HTTPException(status_code=503, detail="Metrics not available")
    return await prometheus_exporter.get_json()


@app.get("/api/v1/dashboard")
async def api_dashboard():
    """Health dashboard endpoint."""
    if not V70_MODULES_LOADED:
        raise HTTPException(status_code=503, detail="Dashboard not available")
    return await health_dashboard.get_dashboard()


@app.get("/api/v1/quality/agents")
async def api_quality_agents():
    """Get agent quality statistics."""
    if not V70_MODULES_LOADED:
        return {"error": "Quality controller not available"}
    
    results = {}
    for agent_id in dispatcher.agents.keys():
        results[agent_id] = await quality_controller.get_agent_performance(agent_id)
    return results


@app.post("/api/v1/quality/evaluate")
async def api_quality_evaluate(request: TaskRequest):
    """Evaluate agent output quality."""
    if not V70_MODULES_LOADED:
        return {"error": "Quality controller not available"}
    
    result = await quality_controller.evaluate(
        agent_id=request.type,
        code=request.payload.get("code", ""),
        requirements=request.payload.get("requirements", ""),
    )
    return result


@app.get("/api/v1/memory/forgetting")
async def api_memory_forgetting():
    """Get forgetting curve statistics."""
    if not V70_MODULES_LOADED:
        return {"error": "Forgetting curve not available"}
    
    return forgetting_curve.get_stats()


@app.post("/api/v1/memory/forgetting/review/{memory_id}")
async def api_memory_review(memory_id: str, quality: int = 3):
    """Review a memory item (spaced repetition)."""
    if not V70_MODULES_LOADED:
        return {"error": "Forgetting curve not available"}
    
    result = forgetting_curve.review_memory(memory_id, quality)
    if result is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return result


@app.get("/api/v1/context/stats")
async def api_context_stats():
    """Get context window statistics."""
    if not V70_MODULES_LOADED:
        return {"error": "Context manager not available"}
    
    return context_manager.get_stats()


@app.post("/api/v1/webhooks")
async def api_create_webhook(name: str, url: str, secret: Optional[str] = None):
    """Create a webhook."""
    if not V70_MODULES_LOADED:
        return {"error": "Webhook manager not available"}
    
    webhook_id = webhook_manager.register_webhook(name, url, secret)
    return {"success": True, "webhook_id": webhook_id}


@app.get("/api/v1/webhooks")
async def api_list_webhooks():
    """List all webhooks."""
    if not V70_MODULES_LOADED:
        return {"error": "Webhook manager not available"}
    
    return {"webhooks": webhook_manager.list_webhooks()}


@app.post("/webhooks/github")
async def webhook_github(request: Request):
    """GitHub webhook endpoint."""
    if not V70_MODULES_LOADED:
        raise HTTPException(status_code=503, detail="Webhook manager not available")
    
    payload = await request.json()
    event = request.headers.get("X-GitHub-Event", "push")
    
    await webhook_manager.handle_event(f"github.{event}", payload)
    return {"success": True}


@app.post("/webhooks/slack")
async def webhook_slack(request: Request):
    """Slack webhook endpoint."""
    if not V70_MODULES_LOADED:
        raise HTTPException(status_code=503, detail="Webhook manager not available")
    
    payload = await request.body()
    await webhook_manager.handle_event("slack.interaction", {"raw": payload.decode()})
    return {"success": True}


@app.post("/api/v1/api-keys")
async def api_create_key(name: str, tier: str = "free"):
    """Create an API key."""
    if not V70_MODULES_LOADED:
        return {"error": "API gateway not available"}
    
    key, metadata = api_gateway.generate_key(name, tier)
    return {"key": key, "metadata": metadata}


@app.get("/api/v1/api-keys")
async def api_list_keys():
    """List API keys."""
    if not V70_MODULES_LOADED:
        return {"error": "API gateway not available"}
    
    return {"keys": api_gateway.list_keys()}


# ── v7.0 Middleware ──────────────────────────────────────────

@app.middleware("http")
async def v7_security_headers(request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    
    if V70_MODULES_LOADED:
        for key, value in SecurityHeaders.get_headers().items():
            response.headers[key] = value
    
    response.headers["X-AIOS-Version"] = "7.0.0"
    return response


# ── Entry point ───────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port      = int(os.environ.get("ORCHESTRATOR_PORT", 8000))
    log_level = LOG_LEVEL.lower()

    configured_keys = [k for k, v in {
        "OPENAI": OPENAI_API_KEY, "ANTHROPIC": ANTHROPIC_API_KEY,
        "GOOGLE": GOOGLE_API_KEY, "DEEPSEEK": DEEPSEEK_API_KEY,
        "GROQ": GROQ_API_KEY,
    }.items() if v]

    print(f"""
    ██████╗ AI Engineering OS v7.0
    ├── Version:        7.0.0
    ├── Environment:     {APP_ENV}
    ├── Orchestrator:   FastAPI on 0.0.0.0:{port}
    ├── Dispatcher:     Async with file locking + SSE
    ├── Memory:         Permanent JSON + Vector + Forgetting Curve
    ├── Planning:       Pre-execution plan generator
    ├── Verification:   Post-build checker
    ├── Agents:         OpenHands·Aider·Bolt·Replit
    ├── API keys:       {', '.join(configured_keys) if configured_keys else 'none configured (agents run in offline mode)'}
    ├── Database:       {DATABASE_URL}
    ├── Dashboard:      http://0.0.0.0:{port}/dashboard
    ├── Docs:           http://0.0.0.0:{port}/docs
    ├── Metrics:        http://0.0.0.0:{port}/api/v1/metrics
    └── v7.0 Modules:   {'Loaded' if V70_MODULES_LOADED else 'Partially loaded (graceful degradation)'}
    """)

    # Start v7.0 components - will be started by uvicorn's lifespan
    # asyncio tasks are started when the app begins
    
    uvicorn.run(
        "orchestrator.main:app",
        host="0.0.0.0",
        port=port,
        log_level=log_level,
        reload=(APP_ENV == "development"),
    )
