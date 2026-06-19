"""
Consistency checker — ensures new code doesn't break existing conventions,
duplicate functions, or contradict schemas.
"""

import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def _extract_function_names(code: str) -> List[str]:
    try:
        tree = ast.parse(code)
        return [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
    except SyntaxError:
        return []


def _extract_class_names(code: str) -> List[str]:
    try:
        tree = ast.parse(code)
        return [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    except SyntaxError:
        return []


def _check_duplicate_functions(new_code: str, existing_files: Dict[str, str]) -> List[str]:
    issues = []
    new_funcs = set(_extract_function_names(new_code))
    for filepath, existing_code in existing_files.items():
        existing_funcs = set(_extract_function_names(existing_code))
        dupes = new_funcs & existing_funcs
        if dupes:
            issues.append(f"Duplicate function(s) in '{filepath}': {', '.join(sorted(dupes))}")
    return issues


def _check_breaking_api_changes(new_code: str, existing_files: Dict[str, str]) -> List[str]:
    """Detect removed endpoints or changed signatures in routes."""
    issues = []
    # Look for FastAPI/Flask route decorators
    new_routes = set(re.findall(r'@(?:app|router)\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']', new_code))
    for filepath, existing_code in existing_files.items():
        old_routes = set(re.findall(r'@(?:app|router)\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']', existing_code))
        removed = old_routes - new_routes
        if removed and filepath.endswith(".py"):
            for method, path in removed:
                issues.append(f"Removed route {method.upper()} {path} (was in '{filepath}')")
    return issues


def _check_security(new_code: str) -> List[str]:
    issues = []
    patterns = [
        (r"execute\s*\(\s*[f'\"].*\{", "Possible SQL injection via f-string in execute()"),
        (r'os\.system\(', "os.system() detected — prefer subprocess"),
        (r'eval\s*\(', "eval() is dangerous — avoid"),
        (r'exec\s*\(', "exec() is dangerous — avoid"),
        (r'pickle\.loads?\(', "pickle.load is insecure with untrusted data"),
        (r'subprocess\.call\(.*shell\s*=\s*True', "subprocess with shell=True is a code injection risk"),
    ]
    for pattern, message in patterns:
        if re.search(pattern, new_code, re.IGNORECASE):
            issues.append(f"Security: {message}")
    return issues


def _check_pep8_basics(new_code: str) -> List[str]:
    """Lightweight PEP8 checks without installing pycodestyle."""
    issues = []
    lines = new_code.splitlines()
    for i, line in enumerate(lines, 1):
        if len(line) > 120:
            issues.append(f"Line {i}: Line too long ({len(line)} > 120 chars)")
        if line != line.rstrip():
            issues.append(f"Line {i}: Trailing whitespace")
    return issues


def check_consistency(new_code: str, existing_codebase: Dict[str, str]) -> Dict[str, Any]:
    """
    Check if new_code is consistent with the existing codebase.

    Args:
        new_code: the code to check
        existing_codebase: dict of {filepath: code_content} for existing files

    Returns:
        {"consistent": bool, "issues": [...], "warnings": [...]}
    """
    issues: List[str] = []
    warnings: List[str] = []

    issues += _check_duplicate_functions(new_code, existing_codebase)
    issues += _check_breaking_api_changes(new_code, existing_codebase)
    issues += _check_security(new_code)

    pep8 = _check_pep8_basics(new_code)
    warnings += pep8

    return {
        "consistent": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


def scan_workspace(workspace_path: str = "workspaces") -> Dict[str, str]:
    """Load all Python files from workspace for consistency checks."""
    result = {}
    base = Path(workspace_path)
    if not base.exists():
        return result
    for py_file in base.rglob("*.py"):
        try:
            result[str(py_file)] = py_file.read_text(errors="replace")
        except Exception:
            pass
    return result
