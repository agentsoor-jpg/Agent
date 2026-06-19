"""
core/dependency_tracker.py - Dependency Tracking v7.1
Scans Python projects, builds import dependency graphs, detects broken imports.
"""

import ast
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class DependencyTracker:
    """Track and analyze Python project dependencies."""
    
    def __init__(self):
        self._cache: Dict[str, Dict] = {}
    
    def scan_project(self, project_path: str) -> Dict[str, Any]:
        """Scan project and build dependency graph."""
        project_path = Path(project_path)
        
        if not project_path.exists():
            return {"error": "Project not found", "files": []}
        
        files = list(project_path.rglob("*.py"))
        
        graph = {
            "files": {},
            "imports": defaultdict(list),
            "dependents": defaultdict(list),
        }
        
        for file_path in files:
            rel_path = str(file_path.relative_to(project_path))
            
            try:
                content = file_path.read_text()
                imports = self._extract_imports(content, file_path)
                
                graph["files"][rel_path] = {
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "imports": imports,
                }
                
                for imp in imports:
                    graph["imports"][imp].append(rel_path)
                    graph["dependents"][rel_path].append(imp)
                    
            except (UnicodeDecodeError, IOError):
                continue
        
        return {
            "project": str(project_path),
            "total_files": len(graph["files"]),
            "graph": {
                "files": dict(graph["files"]),
                "imports": dict(graph["imports"]),
                "dependents": dict(graph["dependents"]),
            }
        }
    
    def _extract_imports(self, content: str, file_path: Path) -> List[str]:
        """Extract import statements from Python file."""
        imports = []
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                        
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
                    for alias in node.names:
                        if node.module:
                            imports.append(f"{node.module}.{alias.name}")
                        else:
                            imports.append(alias.name)
                            
        except SyntaxError:
            pass
        
        return imports
    
    def check_broken_imports(self, project_path: str) -> List[Dict[str, Any]]:
        """Find imports that don't exist in the project."""
        project_path = Path(project_path)
        scan = self.scan_project(str(project_path))
        
        if "error" in scan:
            return [{"error": scan["error"]}]
        
        graph = scan["graph"]
        project_imports = set(graph["files"].keys())
        
        broken = []
        
        for file_path, data in graph["files"].items():
            for imp in data.get("imports", []):
                # Check if it's a relative import (internal)
                if imp.startswith("."):
                    continue
                
                # Check if it's a stdlib module
                stdlib = {
                    "os", "sys", "json", "time", "datetime", "re", "math",
                    "collections", "itertools", "functools", "random", "uuid",
                    "pathlib", "typing", "asyncio", "logging", "traceback",
                    "warnings", "copy", "pickle", "sqlite3", "csv", "io",
                }
                
                if imp.split(".")[0] in stdlib:
                    continue
                
                # Check if it's an internal project file
                top_module = imp.split(".")[0]
                matching_files = [f for f in project_imports if f.startswith(f"{top_module.replace('.', '/')}")]
                
                if not matching_files:
                    broken.append({
                        "file": file_path,
                        "broken_import": imp,
                        "type": "missing_module"
                    })
        
        return broken
    
    def get_dependents(self, project_path: str, file_path: str) -> List[str]:
        """Get files that import the given file."""
        scan = self.scan_project(project_path)
        
        if "error" in scan:
            return []
        
        graph = scan["graph"]
        file_name = Path(file_path).name.replace(".py", "")
        
        dependents = []
        
        for fp, data in graph["files"].items():
            imports = data.get("imports", [])
            if any(file_name in imp or imp.startswith(file_name) for imp in imports):
                dependents.append(fp)
        
        return dependents
    
    def get_dependencies(self, project_path: str, file_path: str) -> List[str]:
        """Get files that this file imports."""
        scan = self.scan_project(project_path)
        
        if "error" in scan:
            return []
        
        graph = scan["graph"]
        rel_path = str(Path(file_path).relative_to(project_path))
        
        return graph["files"].get(rel_path, {}).get("imports", [])
    
    def impact_analysis(self, project_path: str, file_path: str) -> Dict[str, Any]:
        """Analyze what breaks if this file changes."""
        project_path = Path(project_path)
        rel_path = str(Path(file_path).relative_to(project_path))
        
        scan = self.scan_project(str(project_path))
        
        if "error" in scan:
            return {"error": scan["error"]}
        
        graph = scan["graph"]
        
        dependents = self.get_dependents(str(project_path), file_path)
        
        # Find transitive dependents
        all_affected = set(dependents)
        checked = set()
        queue = list(dependents)
        
        while queue:
            current = queue.pop(0)
            if current in checked:
                continue
            checked.add(current)
            
            transitive = self.get_dependents(str(project_path), project_path / current)
            for dep in transitive:
                if dep not in all_affected:
                    all_affected.add(dep)
                    queue.append(dep)
        
        return {
            "file": rel_path,
            "direct_dependents": dependents,
            "all_affected": list(all_affected),
            "impact_score": len(all_affected) + 1,
            "severity": "critical" if len(all_affected) > 5 else "high" if len(all_affected) > 2 else "medium" if all_affected else "low",
        }
    
    def export_json(self, project_path: str) -> str:
        """Export dependency graph as JSON."""
        scan = self.scan_project(project_path)
        return json.dumps(scan, indent=2)
    
    def export_dot(self, project_path: str) -> str:
        """Export dependency graph as DOT format for visualization."""
        scan = self.scan_project(project_path)
        
        if "error" in scan:
            return ""
        
        lines = ["digraph dependencies {"]
        lines.append("  rankdir=LR;")
        lines.append("  node [shape=box];")
        
        graph = scan["graph"]
        
        for file_path in graph["files"]:
            node_name = file_path.replace("/", "_").replace(".", "_")
            lines.append(f'  "{node_name}" [label="{file_path}"];')
        
        for file_path, data in graph["files"].items():
            from_node = file_path.replace("/", "_").replace(".", "_")
            
            for imp in data.get("imports", [])[:5]:  # Limit to avoid clutter
                to_node = imp.replace(".", "_")
                lines.append(f'  "{from_node}" -> "{to_node}";')
        
        lines.append("}")
        
        return "\n".join(lines)


# Global instance
dependency_tracker = DependencyTracker()
