"""
Orchestrator - Unified main entry point.
Launches the Flask REST API and boots the Redis Pub/Sub listener background worker.
"""

import os
import logging
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
from loguru import logger as loguru_logger

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orchestrator")

app = Flask(__name__)
CORS(app)  # Enable cross-origin requests for easy client integration

# Import and initialize subsystems
from orchestrator.meta_agent import MetaAgent
from orchestrator.router import Router
from infra.redis_pubsub import RedisPubSub
from orchestrator.workflow_engine import WorkflowEngine

# Workspace root configuration
WORKSPACE_ROOT = os.getenv("WORKSPACE_ROOT", "./workspace_run")
os.makedirs(WORKSPACE_ROOT, exist_ok=True)

# Shared Singletons
meta_agent = MetaAgent(workspace_root=WORKSPACE_ROOT)
router = Router()
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
pubsub = RedisPubSub(redis_url)
workflow_engine = WorkflowEngine(router=router, pubsub=pubsub)

# Keep track of active workflows in memory
workflow_history = {}


def handle_pubsub_message(channel: str, data: str):
    """Callback for Redis Pub/Sub channel notifications."""
    logger.info(f"Background Worker received on '{channel}': {data}")
    # Run simulated background tasks or routing updates if necessary


# Subscribe background worker to relevant channels
pubsub.subscribe("agent:orchestrator:in", handle_pubsub_message)


@app.route("/")
def index():
    return jsonify({
        "service": "AI Engineering OS - Orchestrator",
        "version": "6.0",
        "status": "running",
        "meta_agent_loaded": meta_agent is not None,
        "redis_connected": pubsub.client is not None,
        "workspace_root": os.path.abspath(WORKSPACE_ROOT)
    })


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "redis_connected": pubsub.client is not None
    })


@app.route("/meta/execute", methods=["POST"])
def execute_goal():
    """Execute a software engineering task end-to-end via the Meta-Agent Layer."""
    data = request.get_json() or {}
    goal = data.get("goal") or data.get("prompt")
    mode = data.get("mode", "safe")  # safe, fast, strict

    if not goal:
        return jsonify({"error": "No goal provided"}), 400

    logger.info(f"Received execute_goal request: '{goal}' [Mode: {mode}]")
    
    try:
        # Run execution plan end-to-end using our ExecutionEngine layer
        result = meta_agent.process_goal(goal, mode=mode)
        
        # Save workflow execution log
        wf_id = f"wf_{int(__import__('time').time())}"
        workflow_history[wf_id] = {
            "id": wf_id,
            "goal": goal,
            "mode": mode,
            "status": result["status"],
            "plan": result["plan"],
            "results": result["results"],
            "workspace_files": result["workspace_files"]
        }
        
        result["workflow_id"] = wf_id
        return jsonify(result)
    except Exception as e:
        logger.exception("Meta-Agent execution crash")
        return jsonify({"error": "MetaAgent failed", "message": str(e)}), 500


@app.route("/meta/workflows", methods=["GET"])
def list_workflows():
    return jsonify(list(workflow_history.values()))


@app.route("/meta/workflow/<workflow_id>", methods=["GET"])
def get_workflow(workflow_id):
    wf = workflow_history.get(workflow_id)
    if not wf:
        return jsonify({"error": "Workflow not found"}), 404
    return jsonify(wf)


@app.route("/meta/workspace/files", methods=["GET"])
def get_workspace_files():
    """Returns absolute file listings and contents inside the secure execution workspace."""
    try:
        files = []
        for root, dirs, filenames in os.walk(WORKSPACE_ROOT):
            for f in filenames:
                rel_path = os.path.relpath(os.path.join(root, f), WORKSPACE_ROOT)
                files.append({
                    "name": f,
                    "path": rel_path,
                    "size": os.path.getsize(os.path.join(root, f))
                })
        return jsonify({"workspace": os.path.abspath(WORKSPACE_ROOT), "files": files})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Launching AI Engineering OS on port {port}...")
    app.run(host="0.0.0.0", port=port)
