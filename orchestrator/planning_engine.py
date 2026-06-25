"""
Planning Engine - Generates ordered execution plans with subtasks.
"""

from typing import List, Dict, Any


class PlanningEngine:
    def create_plan(self, goal: str, task_type: str, complexity: str) -> List[Dict[str, Any]]:
        plan = []

        if task_type == "full_app_build":
            plan = [
                {"step": 1, "action": "analyze_requirements", "agent": "general", "file": "requirements_spec.txt"},
                {"step": 2, "action": "create_project_structure", "agent": "openhands", "path": "src", "file": "src/"},
                {"step": 3, "action": "implement_backend", "agent": "aider", "file": "src/app.py"},
                {"step": 4, "action": "create_frontend", "agent": "bolt", "file": "src/index.html"},
                {"step": 5, "action": "write_tests", "agent": "replit", "file": "src/test_app.py"},
                {"step": 6, "action": "run_tests", "agent": "replit", "file": "src/test_app.py"}
            ]
        elif task_type == "bug_fix":
            plan = [
                {"step": 1, "action": "reproduce_bug", "agent": "replit", "file": "test_bug.py"},
                {"step": 2, "action": "identify_root_cause", "agent": "aider", "file": "src/app.py"},
                {"step": 3, "action": "implement_fix", "agent": "aider", "file": "src/app.py"},
                {"step": 4, "action": "verify_fix", "agent": "replit", "file": "test_bug.py"},
            ]
        elif task_type == "refactor":
            plan = [
                {"step": 1, "action": "understand_task", "agent": "general", "file": "src/app.py"},
                {"step": 2, "action": "execute_task", "agent": "aider", "file": "src/app.py"},
                {"step": 3, "action": "run_tests", "agent": "replit", "file": "src/test_app.py"}
            ]
        else:
            plan = [
                {"step": 1, "action": "understand_task", "agent": "general", "file": "audit_log.txt"},
                {"step": 2, "action": "execute_task", "agent": "aider", "file": "app.py"},
            ]

        return plan
