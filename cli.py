#!/usr/bin/env python3
"""
cli.py - AI Engineering OS CLI v7.0
Command-line interface for managing the AI Engineering OS.
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── ANSI Colors ────────────────────────────────────────────────────────────────

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def color(text: str, c: str) -> str:
    return f"{c}{text}{Colors.ENDC}"


def success(text: str) -> str:
    return color(f"✓ {text}", Colors.GREEN)


def error(text: str) -> str:
    return color(f"✗ {text}", Colors.RED)


def warning(text: str) -> str:
    return color(f"⚠ {text}", Colors.YELLOW)


def info(text: str) -> str:
    return color(f"ℹ {text}", Colors.CYAN)


def header(text: str) -> str:
    return color(f"\n{text}\n{'=' * len(text)}", Colors.HEADER + Colors.BOLD)


# ── Config ─────────────────────────────────────────────────────────────────────

DEFAULT_HOST = "http://localhost:8080"
CONFIG_DIR = Path.home() / ".config" / "ai-os"
CONFIG_FILE = CONFIG_DIR / "config.json"


def get_config() -> Dict[str, Any]:
    """Load configuration."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    
    return {
        "host": DEFAULT_HOST,
        "api_key": os.getenv("AIOS_API_KEY", ""),
        "timeout": 30,
    }


def save_config(config: Dict[str, Any]):
    """Save configuration."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def get_api_url(path: str = "") -> str:
    """Get full API URL."""
    config = get_config()
    base = config.get("host", DEFAULT_HOST)
    return f"{base}/{path.lstrip('/')}"


# ── HTTP Client ────────────────────────────────────────────────────────────────

async def api_get(path: str) -> Dict[str, Any]:
    """Make GET request to API."""
    import httpx
    
    config = get_config()
    headers = {}
    if config.get("api_key"):
        headers["X-API-Key"] = config["api_key"]
    
    try:
        async with httpx.AsyncClient(timeout=config.get("timeout", 30)) as client:
            response = await client.get(
                get_api_url(path),
                headers=headers
            )
            response.raise_for_status()
            return response.json()
    except httpx.ConnectError:
        print(error(f"Cannot connect to {get_api_url()}"))
        print(info("Make sure the server is running: ai-os start"))
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(error(f"API error: {e.response.status_code}"))
        if e.response.status_code == 401:
            print(info("Set API key: ai-os config set api_key <key>"))
        sys.exit(1)
    except Exception as e:
        print(error(f"Request failed: {e}"))
        sys.exit(1)


async def api_post(path: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Make POST request to API."""
    import httpx
    
    config = get_config()
    headers = {}
    if config.get("api_key"):
        headers["X-API-Key"] = config["api_key"]
    
    try:
        async with httpx.AsyncClient(timeout=config.get("timeout", 30)) as client:
            response = await client.post(
                get_api_url(path),
                json=data,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
    except httpx.ConnectError:
        print(error(f"Cannot connect to {get_api_url()}"))
        print(info("Make sure the server is running: ai-os start"))
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(error(f"API error: {e.response.status_code}"))
        try:
            print(e.response.text)
        except Exception:
            pass
        sys.exit(1)


# ── Commands ──────────────────────────────────────────────────────────────────

async def cmd_start(args):
    """Start the AI Engineering OS server."""
    print(header("Starting AI Engineering OS v7.0"))
    
    port = args.port or os.getenv("ORCHESTRATOR_PORT", "8080")
    
    print(info(f"Starting server on port {port}..."))
    
    try:
        # Check if already running
        try:
            await api_get("health")
            print(warning("Server is already running"))
            return
        except SystemExit:
            pass
        
        # Start server
        env = os.environ.copy()
        env["ORCHESTRATOR_PORT"] = str(port)
        
        process = subprocess.Popen(
            [sys.executable, "orchestrator/main.py"],
            cwd=Path(__file__).parent,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        
        # Wait for server to start
        print(info("Waiting for server to start..."))
        for i in range(30):
            await asyncio.sleep(1)
            try:
                await api_get("health")
                print(success(f"Server started on http://localhost:{port}"))
                print(info(f"Dashboard: http://localhost:{port}/dashboard"))
                print(info(f"API docs: http://localhost:{port}/docs"))
                return
            except SystemExit:
                pass
        
        print(error("Server failed to start within 30 seconds"))
        process.kill()
        sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n" + info("Shutting down..."))
        sys.exit(0)


async def cmd_stop(args):
    """Stop the AI Engineering OS server."""
    print(header("Stopping AI Engineering OS"))
    
    try:
        await api_post("shutdown", {})
        print(success("Server stopped"))
    except SystemExit:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                await client.post(get_api_url("shutdown"))
        except Exception:
            pass
        print(success("Server stopped"))
    except Exception as e:
        print(error(f"Failed to stop server: {e}"))
        print(info("You may need to kill the process manually"))


async def cmd_status(args):
    """Get server status."""
    print(header("AI Engineering OS Status"))
    
    try:
        health = await api_get("health")
        
        print(f"\n{'Service:':<20} {health.get('service', 'unknown')}")
        print(f"{'Version:':<20} {health.get('version', 'unknown')}")
        print(f"{'Status:':<20} ", end="")
        if health.get('status') == 'healthy':
            print(success("Healthy"))
        else:
            print(warning(health.get('status', 'unknown')))
        
        print(f"{'Active Workflows:':<20} {health.get('active_workflows', 0)}")
        print(f"{'Queue Size:':<20} {health.get('queue_size', 0)}")
        print(f"{'File Locks:':<20} {health.get('file_locks', 0)}")
        print(f"{'Memory Projects:':<20} {health.get('memory_projects', 0)}")
        
        if args.verbose:
            print("\n" + header("Agents"))
            agents = await api_get("agents/status")
            for agent_id, status in agents.get("agents", {}).items():
                status_str = success("online") if status.get("healthy") else warning("offline")
                print(f"  {agent_id:<15} {status_str}")
            
            print("\n" + header("Workflows"))
            workflows = await api_get("workflows")
            for wf in workflows.get("workflows", []):
                print(f"  - {wf.get('type', 'unknown')}")
    
    except SystemExit:
        print(error("Server is not running"))
        print(info("Start with: ai-os start"))


async def cmd_project_list(args):
    """List all projects."""
    print(header("Projects"))
    
    result = await api_get("memory/projects")
    projects = result.get("projects", [])
    
    if not projects:
        print(warning("No projects found"))
        return
    
    print(f"\nTotal: {len(projects)} projects\n")
    
    for project in projects:
        print(f"  {Colors.BOLD}{project.get('name', 'Unnamed')}{Colors.ENDC}")
        print(f"    ID: {project.get('id', 'N/A')[:8]}...")
        print(f"    Description: {project.get('description', 'N/A')}")
        print(f"    Updated: {datetime.fromtimestamp(project.get('updated_at', 0)).strftime('%Y-%m-%d %H:%M')}")
        print()


async def cmd_project_create(args):
    """Create a new project."""
    print(header("Create Project"))
    
    name = args.name
    description = args.description or ""
    
    data = {
        "name": name,
        "description": description,
    }
    
    result = await api_post("memory/projects", data)
    
    if result.get("success"):
        print(success(f"Project '{name}' created"))
        print(f"  Project ID: {result.get('project_id')}")
    else:
        print(error("Failed to create project"))
        sys.exit(1)


async def cmd_project_delete(args):
    """Delete a project."""
    print(header("Delete Project"))
    
    confirm = input(f"Are you sure you want to delete project '{args.name}'? [y/N] ")
    
    if confirm.lower() != 'y':
        print(info("Cancelled"))
        return
    
    # Note: Would need DELETE endpoint
    print(warning("Delete not implemented in API yet"))


async def cmd_agent_list(args):
    """List all agents."""
    print(header("Agents"))
    
    result = await api_get("agents/status")
    
    print(f"\nOnline: {result.get('online_count', 0)}/{result.get('total', 0)} agents\n")
    
    for agent_id, status in result.get("agents", {}).items():
        status_icon = success("●") if status.get("healthy") else error("○")
        status_text = "online" if status.get("healthy") else "offline"
        
        print(f"  {status_icon} {Colors.BOLD}{agent_id}{Colors.ENDC}")
        print(f"      Status: {status_text}")
        if status.get("tasks_completed"):
            print(f"      Tasks: {status.get('tasks_completed')}")
        print()


async def cmd_agent_start(args):
    """Start an agent."""
    print(header(f"Starting Agent: {args.name}"))
    
    # Start agent via API
    result = await api_post(f"agents/{args.name}/start", {})
    
    if result.get("success"):
        print(success(f"Agent '{args.name}' started"))
    else:
        print(error(f"Failed to start agent"))
        sys.exit(1)


async def cmd_agent_stop(args):
    """Stop an agent."""
    print(header(f"Stopping Agent: {args.name}"))
    
    result = await api_post(f"agents/{args.name}/stop", {})
    
    if result.get("success"):
        print(success(f"Agent '{args.name}' stopped"))
    else:
        print(error(f"Failed to stop agent"))
        sys.exit(1)


async def cmd_workflow_run(args):
    """Run a workflow."""
    print(header(f"Running Workflow: {args.type}"))
    
    data = {
        "requirements": args.requirements,
    }
    
    if args.stack:
        data["stack"] = args.stack
    
    if args.features:
        data["features"] = args.features.split(",")
    
    result = await api_post(f"workflows/{args.type}", data)
    
    if result.get("success"):
        print(success("Workflow started"))
        print(f"  Workflow ID: {result.get('workflow_id')}")
        print(f"  Type: {result.get('workflow_type')}")
        print(f"  Steps: {result.get('steps_completed', 0)}")
        
        if args.wait:
            await cmd_workflow_status_watch(result.get('workflow_id'))
    else:
        print(error("Workflow failed to start"))
        print(f"  Error: {result.get('error', 'Unknown error')}")
        sys.exit(1)


async def cmd_workflow_status(args):
    """Get workflow status."""
    print(header(f"Workflow Status: {args.id}"))
    
    result = await api_get(f"workflows/{args.id}/status")
    
    print(f"\n{'ID:':<20} {result.get('id', args.id)}")
    print(f"{'Type:':<20} {result.get('type', 'unknown')}")
    print(f"{'Status:':<20} ", end="")
    
    status = result.get("status", "unknown")
    if status == "completed":
        print(success(status))
    elif status == "failed":
        print(error(status))
    else:
        print(warning(status))
    
    print(f"{'Steps:':<20} {len(result.get('results', []))}")
    
    if result.get("created_at"):
        print(f"{'Created:':<20} {datetime.fromtimestamp(result.get('created_at')).strftime('%Y-%m-%d %H:%M:%S')}")


async def cmd_workflow_status_watch(workflow_id: str):
    """Watch workflow status."""
    print(info("\nWatching workflow progress... (Ctrl+C to stop)\n"))
    
    try:
        while True:
            result = await api_get(f"workflows/{workflow_id}/status")
            
            status = result.get("status", "unknown")
            
            if status == "completed":
                print(success(f"\nWorkflow completed!"))
                return
            elif status == "failed":
                print(error(f"\nWorkflow failed: {result.get('error', 'Unknown')}\n"))
                return
            
            results = result.get("results", [])
            print(f"\rSteps: {len(results)} | Status: {status}     ", end="", flush=True)
            
            await asyncio.sleep(2)
    except KeyboardInterrupt:
        print("\n" + info("Stopped watching"))


async def cmd_workflow_cancel(args):
    """Cancel a running workflow."""
    print(header(f"Cancelling Workflow: {args.id}"))
    
    result = await api_post(f"workflows/{args.id}/cancel", {})
    
    if result.get("success"):
        print(success("Workflow cancelled"))
    else:
        print(error("Failed to cancel workflow"))
        sys.exit(1)


async def cmd_workflow_list(args):
    """List all workflows."""
    print(header("Workflows"))
    
    result = await api_get("workflows")
    workflows = result.get("workflows", [])
    
    if not workflows:
        print(warning("No workflows found"))
        return
    
    print(f"\nTotal: {len(workflows)} workflows\n")
    
    for wf in workflows:
        status = wf.get("status", "unknown")
        status_color = success if status == "completed" else error if status == "failed" else warning
        
        print(f"  {Colors.BOLD}{wf.get('type', 'unknown')}{Colors.ENDC} ({wf.get('id', '')[:8]}...)")
        print(f"    Status: {status_color(status)}")
        print(f"    Steps: {len(wf.get('results', []))}")
        if wf.get("updated_at"):
            print(f"    Updated: {datetime.fromtimestamp(wf.get('updated_at')).strftime('%Y-%m-%d %H:%M')}")
        print()


async def cmd_memory_search(args):
    """Search memory."""
    print(header("Memory Search"))
    
    result = await api_post("memory/search", {"requirements": args.query})
    
    results = result.get("results", [])
    
    if not results:
        print(warning("No matching projects found"))
        return
    
    print(f"\nFound {len(results)} matching projects:\n")
    
    for proj in results:
        print(f"  {Colors.BOLD}{proj.get('name', 'Unnamed')}{Colors.ENDC}")
        print(f"    Similarity: {proj.get('_similarity_score', 0):.2%}")
        print(f"    {proj.get('description', 'N/A')}")
        print()


async def cmd_memory_export(args):
    """Export memory to file."""
    print(header("Export Memory"))
    
    result = await api_get("memory/projects")
    projects = result.get("projects", [])
    
    output_file = Path(args.output)
    output_file.write_text(json.dumps(projects, indent=2))
    
    print(success(f"Exported {len(projects)} projects to {output_file}"))


async def cmd_memory_import(args):
    """Import memory from file."""
    print(header("Import Memory"))
    
    input_file = Path(args.file)
    
    if not input_file.exists():
        print(error(f"File not found: {input_file}"))
        sys.exit(1)
    
    projects = json.loads(input_file.read_text())
    
    imported = 0
    for project in projects:
        result = await api_post("memory/projects", project)
        if result.get("success"):
            imported += 1
    
    print(success(f"Imported {imported} projects"))


async def cmd_config_get(args):
    """Get configuration value."""
    config = get_config()
    
    if args.key == "all":
        print(json.dumps(config, indent=2))
    elif args.key in config:
        print(config[args.key])
    else:
        print(error(f"Unknown key: {args.key}"))
        sys.exit(1)


async def cmd_config_set(args):
    """Set configuration value."""
    config = get_config()
    config[args.key] = args.value
    save_config(config)
    print(success(f"Set {args.key} = {args.value}"))


async def cmd_logs(args):
    """View logs."""
    print(header("Logs"))
    
    log_file = Path("server.log")
    
    if not log_file.exists():
        print(warning("No log file found"))
        return
    
    lines = log_file.read_text().splitlines()
    
    if args.lines:
        lines = lines[-args.lines:]
    
    for line in lines:
        print(line)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AI Engineering OS CLI v7.0",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start the server")
    start_parser.add_argument("-p", "--port", type=int, help="Port to run on")
    start_parser.set_defaults(func=cmd_start)
    
    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop the server")
    stop_parser.set_defaults(func=cmd_stop)
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Get server status")
    status_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    status_parser.set_defaults(func=cmd_status)
    
    # Project commands
    project_parser = subparsers.add_parser("project", help="Project management")
    project_subparsers = project_parser.add_subparsers(dest="subcommand")
    
    project_list = project_subparsers.add_parser("list", help="List projects")
    project_list.set_defaults(func=cmd_project_list)
    
    project_create = project_subparsers.add_parser("create", help="Create project")
    project_create.add_argument("name", help="Project name")
    project_create.add_argument("-d", "--description", help="Project description")
    project_create.set_defaults(func=cmd_project_create)
    
    project_delete = project_subparsers.add_parser("delete", help="Delete project")
    project_delete.add_argument("name", help="Project name")
    project_delete.set_defaults(func=cmd_project_delete)
    
    # Agent commands
    agent_parser = subparsers.add_parser("agent", help="Agent management")
    agent_subparsers = agent_parser.add_subparsers(dest="subcommand")
    
    agent_list = agent_subparsers.add_parser("list", help="List agents")
    agent_list.set_defaults(func=cmd_agent_list)
    
    agent_start = agent_subparsers.add_parser("start", help="Start agent")
    agent_start.add_argument("name", help="Agent name")
    agent_start.set_defaults(func=cmd_agent_start)
    
    agent_stop = agent_subparsers.add_parser("stop", help="Stop agent")
    agent_stop.add_argument("name", help="Agent name")
    agent_stop.set_defaults(func=cmd_agent_stop)
    
    # Workflow commands
    workflow_parser = subparsers.add_parser("workflow", help="Workflow management")
    workflow_subparsers = workflow_parser.add_subparsers(dest="subcommand")
    
    workflow_run = workflow_subparsers.add_parser("run", help="Run workflow")
    workflow_run.add_argument("type", help="Workflow type")
    workflow_run.add_argument("requirements", help="Requirements")
    workflow_run.add_argument("-s", "--stack", help="Tech stack")
    workflow_run.add_argument("-f", "--features", help="Features (comma-separated)")
    workflow_run.add_argument("-w", "--wait", action="store_true", help="Wait for completion")
    workflow_run.set_defaults(func=cmd_workflow_run)
    
    workflow_status = workflow_subparsers.add_parser("status", help="Get workflow status")
    workflow_status.add_argument("id", help="Workflow ID")
    workflow_status.set_defaults(func=cmd_workflow_status)
    
    workflow_cancel = workflow_subparsers.add_parser("cancel", help="Cancel workflow")
    workflow_cancel.add_argument("id", help="Workflow ID")
    workflow_cancel.set_defaults(func=cmd_workflow_cancel)
    
    workflow_list = workflow_subparsers.add_parser("list", help="List workflows")
    workflow_list.set_defaults(func=cmd_workflow_list)
    
    # Memory commands
    memory_parser = subparsers.add_parser("memory", help="Memory management")
    memory_subparsers = memory_parser.add_subparsers(dest="subcommand")
    
    memory_search = memory_subparsers.add_parser("search", help="Search memory")
    memory_search.add_argument("query", help="Search query")
    memory_search.set_defaults(func=cmd_memory_search)
    
    memory_export = memory_subparsers.add_parser("export", help="Export memory")
    memory_export.add_argument("output", help="Output file")
    memory_export.set_defaults(func=cmd_memory_export)
    
    memory_import = memory_subparsers.add_parser("import", help="Import memory")
    memory_import.add_argument("file", help="Input file")
    memory_import.set_defaults(func=cmd_memory_import)
    
    # Config commands
    config_parser = subparsers.add_parser("config", help="Configuration")
    config_subparsers = config_parser.add_subparsers(dest="subcommand")
    
    config_get = config_subparsers.add_parser("get", help="Get config value")
    config_get.add_argument("key", help="Key (or 'all')")
    config_get.set_defaults(func=cmd_config_get)
    
    config_set = config_subparsers.add_parser("set", help="Set config value")
    config_set.add_argument("key", help="Key")
    config_set.add_argument("value", help="Value")
    config_set.set_defaults(func=cmd_config_set)
    
    # Logs command
    logs_parser = subparsers.add_parser("logs", help="View logs")
    logs_parser.add_argument("-n", "--lines", type=int, help="Number of lines")
    logs_parser.set_defaults(func=cmd_logs)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Run async command
    func = args.func
    
    # Check if function is async
    import inspect
    if inspect.iscoroutinefunction(func):
        asyncio.run(func(args))
    else:
        func(args)


if __name__ == "__main__":
    main()
