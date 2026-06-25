# AI Engineering OS

A unified, full-stack, multi-agent control and execution system for AI-driven software engineering. This system orchestrates agent behaviors, manages secure workspaces, tracks file/task locks, and executes tasks.

## Official Production Entry Point

The system is deployed as a single unified full-stack application on Render:
- **Backend Service & API Server**: `server.ts` (compiled to `dist/server.cjs`)
- **Frontend SPA Web Interface**: Integrated directly via Vite and served from `dist/`
- **Port**: Listens on the environment `PORT` (defaults to `3000`)
- **Host**: Binds to `0.0.0.0` for container routing

## Unified Execution Path

```
User API / UI HTTP Request
   └── POST /api/meta/execute
         └── IntentEngine (Analyzes Goal & Stack)
               └── PlanningEngine (Generates Ordered Steps)
                     └── ExecutionEngine (Direct Workspace File Operations & Secure Terminal Sandbox)
```

## API Endpoints

### POST `/api/meta/execute`
Start a new software engineering task workflow.
```json
{
  "goal": "Create a simple Python file main.py that prints Hello World, then run it",
  "mode": "safe"
}
```

### GET `/api/meta/workflows`
Retrieves history and execution details of all run workflows.

### GET `/api/meta/workflow/:id`
Retrieves logs, plan, and status of a specific workflow.

### GET `/api/meta/workspace/files`
List all files physically present in the workspace sandbox (`/workspace_run`).

## Development & Deployment commands

- **Build Project**: `npm run build`
- **Run in Development**: `npm run dev`
- **Start in Production**: `npm run start`

## License
MIT
