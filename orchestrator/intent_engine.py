"""
Intent Engine - Analyzes user goals and classifies task types.
"""

import re
from typing import Dict, Any


class IntentEngine:
    def __init__(self):
        self.patterns = {
            "full_app_build": r"(build|create|make).*app|full.*application",
            "bug_fix": r"(fix|debug|repair|resolve).*bug|error",
            "refactor": r"(refactor|clean|improve|optimize).*code",
            "add_feature": r"(add|implement|create).*feature|functionality",
            "test": r"(test|coverage|unit test)",
            "deploy": r"(deploy|publish|release)"
        }

    def analyze(self, goal: str) -> Dict[str, Any]:
        goal_lower = goal.lower()
        task_type = "general"
        confidence = 0.5

        for t_type, pattern in self.patterns.items():
            if re.search(pattern, goal_lower):
                task_type = t_type
                confidence = 0.85
                break

        return {
            "task_type": task_type,
            "confidence": confidence,
            "original_goal": goal,
            "complexity": self._estimate_complexity(goal)
        }

    def _estimate_complexity(self, goal: str) -> str:
        words = len(goal.split())
        if words > 25:
            return "high"
        elif words > 12:
            return "medium"
        return "low"
