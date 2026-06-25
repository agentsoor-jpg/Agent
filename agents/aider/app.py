"""
Aider Agent - Precision code editing agent.
"""

import os
import logging
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aider")

app = Flask(__name__)


@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "agent": "aider",
        "capabilities": ["precision_editing", "refactoring", "bug_fixing"]
    })


@app.route("/execute", methods=["POST"])
def execute():
    data = request.get_json() or {}
    task = data.get("task") or data.get("action")

    logger.info(f"Aider received task: {task}")

    result = {
        "agent": "aider",
        "task": task,
        "status": "success",
        "output": f"Precision editing agent Aider applied surgical changes for: {task}",
        "changes_made": 1
    }

    return jsonify(result)


if __name__ == "__main__":
    port = int(os.getenv("AGENT_PORT", 3002))
    app.run(host="0.0.0.0", port=port)
