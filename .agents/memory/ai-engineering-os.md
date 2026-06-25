---
name: AI Engineering OS setup
description: Key decisions and gotchas for the Python FastAPI orchestrator in this workspace
---

## Port conflict
- Port 8080 is owned by the Node.js API server (`artifacts/api-server`)
- Python orchestrator must run on **8000** via `ORCHESTRATOR_PORT=8000`
- Workflow command: `cd /home/runner/workspace && ORCHESTRATOR_PORT=8000 python -m orchestrator.main`

## Required extra dependency
- `python-multipart` must be installed for the `/files/upload` endpoint (FastAPI UploadFile)
- FastAPI raises RuntimeError at startup if missing — not at request time

## State persistence
- Workflow state is persisted to `state/workflows.json` on every update
- On restart, in-progress workflows are marked `interrupted` (not lost)

## Agent offline handling
- Agents at ports 3001-3004 are Docker-based and expected to be offline in Replit sandbox
- All adapters return `status: "offline"` with a human-readable summary instead of raising
- Workflow continues through fallback chain even when all agents are offline

**Why:** The system must never crash due to agent unavailability — the user runs this in an environment where Docker agents aren't active.

## Fallback chain
- bolt → aider → openhands (no further fallback)
- replit → openhands
- Defined in both `policies/routing-policy.json` and per-step in `policies/workflow-policy.json`

## Context window limits (chars, not tokens)
- openhands: 60,000 chars
- aider: 30,000 chars  
- bolt: 20,000 chars
- replit: 10,000 chars
- `Dispatcher._trim_context()` enforces these before sending context to agents

**Why:** Prevents sending massive codebases to agents with small context windows.
