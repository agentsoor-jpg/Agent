"""
Anti-hallucination validator.
Checks agent outputs for syntax errors, bad imports, placeholder code,
missing file references, and invalid JSON/YAML.
"""

import ast
import importlib.util
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

WORKSPACE = Path("workspaces")

PLACEHOLDER_PATTERNS = [
    r"^\s*pass\s*$",
    r"#\s*(TODO|FIXME|HACK|XXX|PLACEHOLDER)",
    r'("""|\'\'\').*?(TODO|FIXME|implement this|your code here).*?("""|\'\'\')' ,
    r"raise NotImplementedError",
    r"\.\.\.  *# placeholder",
]

FORBIDDEN_SECRETS = [
    r"password\s*=\s*['\"][^'\"]{4,}['\"]",
    r"secret\s*=\s*['\"][^'\"]{4,}['\"]",
    r"api_key\s*=\s*['\"][^'\"]{4,}['\"]",
    r"token\s*=\s*['\"][^'\"]{4,}['\"]",
]


def _check_python_syntax(code: str) -> List[str]:
    errors = []
    try:
        ast.parse(code)
    except SyntaxError as e:
        errors.append(f"SyntaxError at line {e.lineno}: {e.msg}")
    return errors


def _check_imports(code: str) -> List[str]:
    errors = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return errors

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = node.names[0].name if isinstance(node, ast.Import) else node.module
            if not mod:
                continue
            top = mod.split(".")[0]
            # Only check stdlib and well-known packages; skip relative imports
            if top and not top.startswith("_"):
                spec = importlib.util.find_spec(top)
                if spec is None:
                    errors.append(f"Unresolvable import: '{top}' (module not installed)")
    return errors


def _check_placeholders(code: str) -> List[str]:
    errors = []
    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, code, re.IGNORECASE | re.MULTILINE):
            errors.append(f"Placeholder code detected: pattern '{pattern}'")
    return errors


def _check_file_references(code: str) -> List[str]:
    errors = []
    # Look for open() calls with literal string paths
    matches = re.findall(r'open\(["\']([^"\']+)["\']', code)
    for path in matches:
        if path.startswith("/") or ".." in path:
            continue  # skip absolute or relative-parent paths
        if not Path(path).exists() and not (WORKSPACE / path).exists():
            errors.append(f"Referenced file not found: '{path}'")
    return errors


def _check_secrets(code: str) -> List[str]:
    errors = []
    for pattern in FORBIDDEN_SECRETS:
        if re.search(pattern, code, re.IGNORECASE):
            errors.append(f"Hardcoded secret detected: pattern '{pattern}'")
    return errors


def validate_python(code: str, strict: bool = False) -> Dict[str, Any]:
    """Validate Python source code."""
    errors: List[str] = []
    warnings: List[str] = []

    errors += _check_python_syntax(code)
    if not errors:  # Only check imports if syntax is valid
        import_errors = _check_imports(code)
        for e in import_errors:
            warnings.append(e)  # import failures → warnings (env differences)
        errors += _check_placeholders(code)
        if strict:
            errors += _check_file_references(code)
        warnings += _check_secrets(code)

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "language": "python",
    }


def validate_json(content: str) -> Dict[str, Any]:
    errors = []
    try:
        json.loads(content)
    except json.JSONDecodeError as e:
        errors.append(f"JSONDecodeError: {e.msg} at line {e.lineno} col {e.colno}")
    return {"valid": len(errors) == 0, "errors": errors, "language": "json"}


def validate_yaml(content: str) -> Dict[str, Any]:
    if not HAS_YAML:
        return {"valid": True, "errors": [], "warnings": ["yaml not installed, skipped"], "language": "yaml"}
    errors = []
    try:
        yaml.safe_load(content)
    except Exception as e:
        errors.append(f"YAMLError: {e}")
    return {"valid": len(errors) == 0, "errors": errors, "language": "yaml"}


def validate_agent_output(output: Any, task_type: str) -> Dict[str, Any]:
    """
    Validate what an agent returned.
    output: dict from agent adapter
    task_type: e.g. 'scaffold', 'edit', 'fix'
    """
    all_errors: List[str] = []
    all_warnings: List[str] = []
    file_results: Dict[str, dict] = {}

    if not isinstance(output, dict):
        return {"valid": False, "errors": ["Agent output is not a dict"], "warnings": [], "file_results": {}}

    # Check status
    if output.get("status") == "error":
        all_errors.append(f"Agent reported error: {output.get('error', 'unknown')}")

    # Validate any code blocks returned by agent
    code_blocks = output.get("code_blocks", {})
    for filename, code in code_blocks.items():
        ext = Path(filename).suffix.lower()
        if ext == ".py":
            res = validate_python(code)
        elif ext == ".json":
            res = validate_json(code)
        elif ext in (".yaml", ".yml"):
            res = validate_yaml(code)
        else:
            res = {"valid": True, "errors": [], "warnings": []}

        file_results[filename] = res
        all_errors += res.get("errors", [])
        all_warnings += res.get("warnings", [])

    # Check summary is not placeholder
    summary = output.get("summary", "")
    if "TODO" in summary or "placeholder" in summary.lower():
        all_warnings.append("Summary mentions TODO/placeholder")

    return {
        "valid": len(all_errors) == 0,
        "errors": all_errors,
        "warnings": all_warnings,
        "file_results": file_results,
        "task_type": task_type,
    }


def validate_file_content(file_path: str, content: str) -> Dict[str, Any]:
    """Validate a file's content based on its extension."""
    ext = Path(file_path).suffix.lower()
    if ext == ".py":
        return validate_python(content)
    elif ext == ".json":
        return validate_json(content)
    elif ext in (".yaml", ".yml"):
        return validate_yaml(content)
    return {"valid": True, "errors": [], "warnings": [], "language": "unknown"}
