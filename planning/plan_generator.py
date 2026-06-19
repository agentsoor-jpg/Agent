"""
Pre-execution plan generator.
Analyzes requirements, produces a phased architecture plan, and assigns
agents to each phase based on their specialization.
"""

import re
import time
import uuid
from typing import Any, Dict, List, Optional


AGENT_SPECIALIZATIONS = {
    "bolt": ["scaffold", "generate", "prototype", "ui", "frontend", "template"],
    "aider": ["edit", "refactor", "fix", "patch", "update", "modify", "implement"],
    "openhands": ["analyze", "review", "debug", "diagnose", "architecture", "research", "auth", "integration"],
    "replit": ["test", "verify", "run", "check", "validate", "preview"],
}

TECH_STACK_PHASES = {
    "fastapi": ["scaffold", "models", "routes", "auth", "tests"],
    "django": ["scaffold", "models", "views", "urls", "templates", "tests"],
    "react": ["scaffold", "components", "routing", "state", "tests"],
    "nextjs": ["scaffold", "pages", "api_routes", "components", "tests"],
    "express": ["scaffold", "routes", "middleware", "models", "tests"],
    "flask": ["scaffold", "routes", "models", "auth", "tests"],
}

FILE_ESTIMATES = {
    "simple": {"files": (3, 8), "lines": (50, 300), "hours": 0.5},
    "medium": {"files": (8, 20), "lines": (300, 1000), "hours": 2},
    "complex": {"files": (20, 50), "lines": (1000, 5000), "hours": 8},
    "enterprise": {"files": (50, 150), "lines": (5000, 20000), "hours": 40},
}


def _estimate_complexity(requirements: str) -> str:
    text = requirements.lower()
    word_count = len(text.split())

    complex_signals = [
        "microservice", "distributed", "kubernetes", "oauth", "real-time",
        "machine learning", "ml", "ai", "blockchain", "enterprise", "scale",
        "multi-tenant", "websocket", "streaming",
    ]
    medium_signals = [
        "auth", "authentication", "database", "api", "rest", "graphql",
        "jwt", "postgresql", "redis", "celery", "docker",
    ]

    if any(s in text for s in complex_signals) or word_count > 150:
        return "complex"
    if word_count > 200:
        return "enterprise"
    if any(s in text for s in medium_signals) or word_count > 50:
        return "medium"
    return "simple"


def _detect_stack(requirements: str) -> List[str]:
    text = requirements.lower()
    stacks = []
    keywords = {
        "fastapi": ["fastapi", "fast api"],
        "django": ["django"],
        "react": ["react"],
        "nextjs": ["next.js", "nextjs", "next js"],
        "express": ["express", "node.js", "nodejs"],
        "flask": ["flask"],
        "postgresql": ["postgresql", "postgres", "pg"],
        "mysql": ["mysql"],
        "mongodb": ["mongodb", "mongo"],
        "redis": ["redis"],
        "docker": ["docker", "container"],
        "jwt": ["jwt", "json web token"],
    }
    for tech, kws in keywords.items():
        if any(kw in text for kw in kws):
            stacks.append(tech)
    return stacks


def _detect_features(requirements: str) -> List[str]:
    text = requirements.lower()
    feature_map = {
        "authentication": ["auth", "login", "signup", "jwt", "oauth", "session"],
        "database": ["database", "db", "model", "schema", "orm", "migration"],
        "api": ["api", "rest", "endpoint", "route", "graphql"],
        "frontend": ["ui", "frontend", "dashboard", "component", "page", "view"],
        "testing": ["test", "pytest", "unittest", "spec", "coverage"],
        "deployment": ["docker", "kubernetes", "deploy", "ci/cd", "pipeline"],
        "real_time": ["websocket", "sse", "real-time", "streaming", "socket"],
        "search": ["search", "elasticsearch", "full-text"],
        "file_upload": ["upload", "file", "storage", "s3"],
        "email": ["email", "smtp", "notification", "mailgun"],
    }
    detected = []
    for feature, signals in feature_map.items():
        if any(s in text for s in signals):
            detected.append(feature)
    return detected


def _assign_agent(phase_name: str, action: str) -> str:
    action_lower = action.lower()
    for agent, keywords in AGENT_SPECIALIZATIONS.items():
        if any(kw in action_lower or kw in phase_name.lower() for kw in keywords):
            return agent
    return "openhands"


def _build_phases(
    requirements: str,
    stack: List[str],
    features: List[str],
    complexity: str,
) -> List[Dict[str, Any]]:
    phases = []

    # Phase 0: Analysis (always OpenHands)
    phases.append({
        "name": "analysis",
        "description": "Analyze requirements, design architecture, and create file structure plan",
        "agent": "openhands",
        "action": "analyze",
        "files_to_create": ["ARCHITECTURE.md", "file_plan.json"],
        "dependencies": [],
        "estimated_time": "30s",
        "validation": "analysis_complete",
    })

    # Phase 1: Scaffold (Bolt)
    scaffold_files = ["README.md", "requirements.txt"]
    primary_stack = stack[0] if stack else "python"
    if primary_stack in ("fastapi", "flask", "django", "express"):
        scaffold_files += ["main.py", "config.py", ".env.example"]
    if "docker" in stack:
        scaffold_files += ["Dockerfile", "docker-compose.yml"]

    phases.append({
        "name": "scaffold",
        "description": f"Generate project scaffold and boilerplate for {primary_stack}",
        "agent": "bolt",
        "action": "scaffold",
        "files_to_create": scaffold_files,
        "dependencies": ["analysis"],
        "estimated_time": "45s",
        "validation": "files_created",
    })

    # Phase 2: Core implementation (Aider)
    impl_files = []
    if "database" in features:
        impl_files += ["models.py", "database.py", "migrations/"]
    if "api" in features:
        impl_files += ["routers/", "schemas.py"]
    if "authentication" in features:
        impl_files += ["auth.py", "security.py"]

    phases.append({
        "name": "implementation",
        "description": "Implement core business logic, models, and API routes",
        "agent": "aider",
        "action": "edit",
        "files_to_create": impl_files or ["core.py", "api.py"],
        "dependencies": ["scaffold"],
        "estimated_time": "2m",
        "validation": "files_modified",
    })

    # Phase 3: Feature-specific (OpenHands for complex features)
    if "authentication" in features or "real_time" in features:
        phases.append({
            "name": "advanced_features",
            "description": "Implement authentication, real-time features, and integrations",
            "agent": "openhands",
            "action": "execute",
            "files_to_create": ["middleware.py", "websockets.py"] if "real_time" in features else ["auth_routes.py"],
            "dependencies": ["implementation"],
            "estimated_time": "3m",
            "validation": "features_complete",
        })

    # Phase 4: Tests (Replit)
    if complexity in ("medium", "complex", "enterprise"):
        phases.append({
            "name": "testing",
            "description": "Run tests, verify imports, check all endpoints",
            "agent": "replit",
            "action": "test",
            "files_to_create": ["tests/test_main.py"],
            "dependencies": ["implementation"],
            "estimated_time": "1m",
            "validation": "tests_pass",
        })

    # Phase 5: Review (OpenHands)
    phases.append({
        "name": "review",
        "description": "Code review, security audit, and final validation",
        "agent": "openhands",
        "action": "review",
        "files_to_create": ["REVIEW.md"],
        "dependencies": ["testing"] if complexity != "simple" else ["implementation"],
        "estimated_time": "30s",
        "validation": "review_complete",
    })

    return phases


def _build_component_tree(features: List[str], stack: List[str]) -> Dict[str, Any]:
    root = {"name": "project", "children": []}
    if stack:
        root["children"].append({"name": "backend", "tech": stack[0], "children": [
            {"name": f, "type": "feature"} for f in features
        ]})
    if "frontend" in features or any(s in stack for s in ["react", "nextjs"]):
        root["children"].append({"name": "frontend", "children": [
            {"name": "components", "type": "dir"},
            {"name": "pages", "type": "dir"},
        ]})
    return root


def generate_plan(requirements: str, stack: Optional[str] = None, features: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Generate a detailed execution plan from requirements.

    Returns:
        {
            plan_id, complexity, detected_stack, detected_features,
            phases, component_tree, estimates, created_at
        }
    """
    complexity = _estimate_complexity(requirements)
    detected_stack = _detect_stack(requirements)
    if stack:
        for s in stack.lower().replace(",", " ").split():
            if s not in detected_stack:
                detected_stack.insert(0, s)

    detected_features = _detect_features(requirements)
    if features:
        for f in features:
            if f not in detected_features:
                detected_features.append(f)

    phases = _build_phases(requirements, detected_stack, detected_features, complexity)
    estimates = FILE_ESTIMATES.get(complexity, FILE_ESTIMATES["medium"])

    return {
        "plan_id": str(uuid.uuid4()),
        "requirements": requirements,
        "complexity": complexity,
        "detected_stack": detected_stack,
        "detected_features": detected_features,
        "phases": phases,
        "component_tree": _build_component_tree(detected_features, detected_stack),
        "estimates": {
            "files_min": estimates["files"][0],
            "files_max": estimates["files"][1],
            "lines_min": estimates["lines"][0],
            "lines_max": estimates["lines"][1],
            "estimated_hours": estimates["hours"],
        },
        "total_phases": len(phases),
        "agents_involved": list({p["agent"] for p in phases}),
        "created_at": time.time(),
    }
