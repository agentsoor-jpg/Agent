"""
Completeness checker — compares what was built against what was required.
"""

import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


FEATURE_FILE_SIGNALS = {
    "authentication": ["auth", "login", "jwt", "token", "session", "oauth"],
    "database": ["model", "schema", "migration", "orm", "db", "database"],
    "api": ["route", "endpoint", "router", "api", "controller"],
    "testing": ["test_", "_test", "spec_", "pytest", "unittest"],
    "frontend": ["component", "page", "view", "template", "static"],
    "docker": ["Dockerfile", "docker-compose"],
    "ci_cd": [".github", "Jenkinsfile", ".travis", "gitlab-ci"],
    "documentation": ["README", "ARCHITECTURE", "docs/"],
    "real_time": ["websocket", "sse", "socket", "stream"],
    "email": ["email", "smtp", "mail", "sendgrid"],
}


def _get_built_files(workspace_path: str) -> List[str]:
    base = Path(workspace_path)
    if not base.exists():
        return []
    return [str(f.relative_to(base)) for f in base.rglob("*") if f.is_file()]


def _detect_required_features(requirements: str) -> List[str]:
    text = requirements.lower()
    found = []
    for feature, signals in FEATURE_FILE_SIGNALS.items():
        if any(s in text for s in signals):
            found.append(feature)
    return found


def _check_feature_present(feature: str, built_files: List[str]) -> bool:
    signals = FEATURE_FILE_SIGNALS.get(feature, [])
    for f in built_files:
        f_lower = f.lower()
        if any(sig.lower() in f_lower for sig in signals):
            return True
    return False


def check_completeness(
    requirements: str,
    built_files: Optional[List[str]] = None,
    workspace_path: str = "workspaces",
) -> Dict[str, Any]:
    """
    Compare built files against requirements.

    Returns:
        {
            complete: bool,
            percentage: float,
            required_features: [...],
            found_features: [...],
            missing_features: [...],
            built_files: [...],
            report: str,
        }
    """
    if built_files is None:
        built_files = _get_built_files(workspace_path)

    required_features = _detect_required_features(requirements)

    if not required_features:
        return {
            "complete": len(built_files) > 0,
            "percentage": 100.0 if built_files else 0.0,
            "required_features": [],
            "found_features": [],
            "missing_features": [],
            "built_files": built_files,
            "file_count": len(built_files),
            "report": "No specific features detected in requirements.",
            "checked_at": time.time(),
        }

    found = [f for f in required_features if _check_feature_present(f, built_files)]
    missing = [f for f in required_features if f not in found]
    percentage = (len(found) / len(required_features)) * 100 if required_features else 100.0

    report_lines = [
        f"Built {len(built_files)} files",
        f"Features: {len(found)}/{len(required_features)} complete ({percentage:.0f}%)",
    ]
    if missing:
        report_lines.append(f"Missing: {', '.join(missing)}")
    if found:
        report_lines.append(f"Present: {', '.join(found)}")

    return {
        "complete": len(missing) == 0,
        "percentage": round(percentage, 1),
        "required_features": required_features,
        "found_features": found,
        "missing_features": missing,
        "built_files": built_files[:50],  # cap for response size
        "file_count": len(built_files),
        "report": " | ".join(report_lines),
        "checked_at": time.time(),
    }
