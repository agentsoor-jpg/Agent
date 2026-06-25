"""
OpenHands Agent - Autonomous execution + debugging agent.
"""

import os
import logging
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("openhands")

app = Flask(__name__)


@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "agent": "openhands",
        "capabilities": ["autonomous_execution", "code_review", "debugging"]
    })


@app.route("/execute", methods=["POST"])
def execute():
    data = request.get_json() or {}
    task = data.get("task") or data.get("action")

    logger.info(f"OpenHands received task: {task}")

    # Basic execution confirmation
    result = {
        "agent": "openhands",
        "task": task,
        "status": "success",
        "output": f"Autonomous execution agent OpenHands completed task: {task}",
        "files_modified": []
    }

    return jsonify(result)


if __name__ == "__main__":
    port = int(os.getenv("AGENT_PORT", 3001))
    app.run(host="0.0.0.0", port=port)
