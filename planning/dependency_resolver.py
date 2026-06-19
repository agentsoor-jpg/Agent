"""
Dependency resolver — determines the correct build order for phases/components
and detects circular dependencies.
"""

from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple


def _build_graph(components: List[Dict[str, Any]]) -> Tuple[Dict[str, List[str]], Dict[str, dict]]:
    """Build adjacency list from component list."""
    graph: Dict[str, List[str]] = defaultdict(list)
    nodes: Dict[str, dict] = {}

    for comp in components:
        name = comp.get("name") or comp.get("phase", f"comp_{id(comp)}")
        nodes[name] = comp
        deps = comp.get("dependencies", [])
        for dep in deps:
            graph[dep].append(name)  # dep must come before name
        if name not in graph:
            graph[name] = []

    return dict(graph), nodes


def _detect_cycles(graph: Dict[str, List[str]]) -> List[List[str]]:
    """Find all cycles using DFS."""
    visited: Set[str] = set()
    rec_stack: Set[str] = set()
    cycles: List[List[str]] = []

    def dfs(node: str, path: List[str]):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, path)
            elif neighbor in rec_stack:
                cycle_start = path.index(neighbor)
                cycles.append(path[cycle_start:] + [neighbor])
        path.pop()
        rec_stack.discard(node)

    for node in list(graph.keys()):
        if node not in visited:
            dfs(node, [])

    return cycles


def _topological_sort(graph: Dict[str, List[str]], nodes: Set[str]) -> List[str]:
    """Kahn's algorithm for topological sort."""
    in_degree: Dict[str, int] = {n: 0 for n in nodes}
    for node, neighbors in graph.items():
        for neighbor in neighbors:
            in_degree[neighbor] = in_degree.get(neighbor, 0) + 1

    queue = deque(n for n in nodes if in_degree.get(n, 0) == 0)
    order = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbor in graph.get(node, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return order


def resolve_order(components: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Resolve the correct build order for a list of components/phases.

    Each component should have:
        - "name" or "phase": unique identifier
        - "dependencies": list of component names that must come first

    Returns:
        {
            "order": [sorted list of names],
            "cycles": [detected cycles, empty if none],
            "resolved": bool,
            "parallel_groups": [[names that can run in parallel]]
        }
    """
    if not components:
        return {"order": [], "cycles": [], "resolved": True, "parallel_groups": []}

    graph, nodes = _build_graph(components)
    all_nodes = set(nodes.keys())

    cycles = _detect_cycles(graph)
    if cycles:
        # Break cycles by removing the last edge in each cycle
        broken = []
        for cycle in cycles:
            if len(cycle) >= 2:
                # Remove edge from second-to-last → last
                src = cycle[-2]
                dst = cycle[-1]
                if dst in graph.get(src, []):
                    graph[src].remove(dst)
                    broken.append(f"{src} → {dst}")

    order = _topological_sort(graph, all_nodes)

    # Build parallel groups (components at same depth can run in parallel)
    depths: Dict[str, int] = {}
    for name in order:
        component = nodes.get(name, {})
        deps = component.get("dependencies", [])
        if not deps:
            depths[name] = 0
        else:
            depths[name] = max(depths.get(d, 0) for d in deps if d in depths) + 1

    max_depth = max(depths.values(), default=0)
    parallel_groups = []
    for depth in range(max_depth + 1):
        group = [n for n, d in depths.items() if d == depth]
        if group:
            parallel_groups.append(group)

    return {
        "order": order,
        "cycles": cycles,
        "resolved": True,
        "parallel_groups": parallel_groups,
        "cycle_breaks": broken if cycles else [],
    }


def get_build_sequence(phases: List[Dict[str, Any]]) -> List[str]:
    """Simple helper — returns just the ordered list of phase names."""
    result = resolve_order(phases)
    return result["order"]
