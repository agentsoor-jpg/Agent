# AI Engineering OS

A hybrid multi-agent AI Engineering Operating System that orchestrates OpenHands, Aider, Bolt, and Replit agents to collaboratively build, refactor, debug, and review complex software projects.

## Run & Operate

- `ORCHESTRATOR_PORT=8000 python -m orchestrator.main` — run the orchestrator (FastAPI, port 8000)
- Dashboard: `GET /dashboard` — live management UI
- API docs: `GET /docs` — FastAPI Swagger UI
- Health: `GET /health`

## Python Dependencies

```
pip install fastapi uvicorn pydantic httpx python-dotenv pyyaml loguru python-multipart
```

## Stack

- **Orchestrator**: FastAPI + uvicorn (port 8000)
- **Agents**: OpenHands (3001), Aider (3002), Bolt (3003), Replit (3004)
- **Policies**: JSON files in `policies/`
- **State**: Persisted to `state/` directory (survives restarts)
- **Dashboard**: Static HTML in `static/index.html`
- **Workspaces**: `workspaces/` for uploaded/generated project files

## Where things live

- `orchestrator/main.py` — FastAPI app, all API endpoints
- `orchestrator/dispatcher.py` — Core: workflow lifecycle, file locking, fallback, async
- `orchestrator/router.py` — Task-to-agent routing from `policies/routing-policy.json`
- `agents/*/adapter.py` — Agent adapters with real httpx calls and offline fallbacks
- `agents/base_agent.py` — Abstract base with health_check, status tracking
- `policies/workflow-policy.json` — 5 workflow definitions with fallback chains
- `policies/routing-policy.json` — Task routing rules + agent boundaries
- `static/index.html` — Full dashboard (dark/light, responsive, real API calls)
- `state/` — Persisted workflow state JSON files

## Architecture decisions

- **Orchestrator is stateless at the request level** — state lives in `state/` on disk
- **File locking** — `FileLock` class prevents concurrent writes to the same file
- **Per-agent asyncio.Semaphore** — enforces max_concurrent limits per agent
- **Fallback chain** — bolt→aider→openhands; each step has a `fallback` field in policy
- **Offline-safe** — agents return structured `status: "offline"` instead of raising; workflow continues
- **Context trimming** — per-agent token limits (openhands:60K, aider:30K, bolt:20K, replit:10K)
- **Smart routing** — `_estimate_complexity()` overrides base routing for simple/complex tasks

## Agent task boundaries (STRICT)

| Agent | Role | Can Create | Can Edit | Max Concurrent |
|-------|------|-----------|---------|----------------|
| Bolt | App scaffolding, UI generation | ✓ | ✗ | 1 |
| Aider | Precise file edits, refactoring | ✗ | ✓ | 2 |
| OpenHands | Autonomous execution, review, debug | ✓ | ✓ | 1 |
| Replit | Run commands, tests, verification | ✗ | ✗ | 2 |

## API Endpoints

```
GET  /health              — System health
GET  /dashboard           — Management UI
GET  /agents/status       — Health check all 4 agents
POST /workflows/{type}    — Run: full-app-generation, refactoring, bug-fixing, prototyping, code-review
GET  /workflows           — List all workflows with status summary
GET  /workflows/{id}/status — Workflow detail
POST /tasks/route         — Route a task to best agent (with complexity analysis)
GET  /env                 — Read .env
POST /env                 — Write .env
GET  /policies            — Read all policy JSON files
POST /policies            — Write a policy file
GET  /files?path=...      — Browse workspace files
POST /files/upload        — Upload file to workspaces/
POST /terminal            — Run shell command (30s timeout)
GET  /locks               — Active file locks
```

## Gotchas

- Port 8080 is taken by the Node.js API server — orchestrator runs on **8000**
- `python-multipart` is required for file upload endpoints
- Run orchestrator from workspace root: `cd /home/runner/workspace && ORCHESTRATOR_PORT=8000 python -m orchestrator.main`
- State persists in `state/` — delete to reset; interrupted workflows are marked on restart
- Agents at 3001-3004 are expected to be offline in this environment (Docker-based) — the system handles it gracefully

## User preferences

- Comprehensive, production-ready implementations — not stubs or placeholders
- All agents must handle offline/unreachable state gracefully without crashing
- Never block the async loop — all external calls use asyncio + httpx with timeouts
