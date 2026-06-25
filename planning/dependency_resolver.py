"""Dependency resolver — topological sort with cycle detection for task ordering.

Given a set of tasks with dependencies, produces a safe execution order.
Detects cycles and groups independent tasks for parallel execution.
"""

from collections import defaultdict, deque
from typing import Any


class DependencyError(Exception):
    """Raised when dependencies cannot be resolved (e.g., cycles)."""
    pass


def resolve_dependencies(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """Resolve task execution order via topological sort.

    Each task dict must have:
        - id: unique task identifier
        - dependencies: list of task IDs this task depends on

    Returns:
        {
            "order": [task_id, ...],          # flat execution order
            "levels": [[task_id, ...], ...],   # grouped by parallel level
            "has_cycle": bool,
            "cycle": [task_id, ...] | None,
        }
    """
    if not tasks:
        return {"order": [], "levels": [], "has_cycle": False, "cycle": None}

    # Build adjacency list and in-degree map
    task_ids = {t["id"] for t in tasks if "id" in t}
    graph: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = {t["id"]: 0 for t in tasks if "id" in t}

    for task in tasks:
        tid = task.get("id")
        if not tid:
            continue
        deps = task.get("dependencies", [])
        for dep in deps:
            if dep not in task_ids:
                # Unknown dependency — treat as external (skip)
                continue
            graph[dep].append(tid)
            in_degree[tid] += 1

    # Kahn's algorithm for topological sort
    queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
    order: list[str] = []
    levels: list[list[str]] = []

    while queue:
        # All tasks in the current queue have no unresolved dependencies
        # — they can run in parallel
        current_level = list(queue)
        levels.append(current_level)
        next_queue: deque[str] = deque()

        for tid in current_level:
            order.append(tid)
            in_degree[tid] = -1  # mark as processed
            for dependent in graph[tid]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    next_queue.append(dependent)

        queue = next_queue

    # Check for cycles
    if len(order) < len(in_degree):
        cycle_nodes = [tid for tid, deg in in_degree.items() if deg > 0]
        return {
            "order": order,
            "levels": levels,
            "has_cycle": True,
            "cycle": cycle_nodes,
        }

    return {
        "order": order,
        "levels": levels,
        "has_cycle": False,
        "cycle": None,
    }


def check_completeness(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """Check if all tasks have required fields and dependencies are valid."""
    errors: list[str] = []
    task_ids = {t.get("id") for t in tasks if t.get("id")}

    for task in tasks:
        tid = task.get("id")
        if not tid:
            errors.append("Task missing 'id' field")
            continue
        if not task.get("agent_id") and not task.get("agent"):
            errors.append(f"Task '{tid}' missing 'agent_id'")
        if not task.get("action"):
            errors.append(f"Task '{tid}' missing 'action'")

        for dep in task.get("dependencies", []):
            if dep not in task_ids:
                errors.append(f"Task '{tid}' depends on unknown task '{dep}'")

    return {
        "complete": len(errors) == 0,
        "errors": errors,
        "task_count": len(tasks),
    }


def get_parallel_groups(tasks: list[dict[str, Any]]) -> list[list[str]]:
    """Return task IDs grouped by parallel execution level."""
    result = resolve_dependencies(tasks)
    if result["has_cycle"]:
        raise DependencyError(f"Dependency cycle detected: {result['cycle']}")
    return result["levels"]
