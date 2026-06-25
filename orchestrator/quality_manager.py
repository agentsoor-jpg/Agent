"""
Quality Manager - Validates agent outputs before acceptance.
"""

from typing import Dict, Any


class QualityManager:
    def validate_output(self, output: Dict[str, Any], task_type: str) -> Dict[str, Any]:
        score = 0.9
        issues = []

        if not output.get("success", True):
            issues.append("Task reported failure")
            score -= 0.4

        content = output.get("content", "")
        if len(str(content)) < 15:
            issues.append("Output response is extremely short or blank")
            score -= 0.3

        return {
            "passed": score >= 0.6,
            "score": round(max(0.0, score), 2),
            "issues": issues
        }
