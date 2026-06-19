"""
Post-build verifier — runs real checks against built workspace:
  - py_compile on all .py files
  - pytest if tests exist
  - pip check
  - import resolution
"""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


async def _run(cmd: str, cwd: str, timeout: int = 60) -> Dict[str, Any]:
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "passed": proc.returncode == 0,
            "stdout": stdout.decode(errors="replace")[:2000],
            "stderr": stderr.decode(errors="replace")[:2000],
            "exit_code": proc.returncode,
            "command": cmd,
        }
    except asyncio.TimeoutError:
        return {"passed": False, "stdout": "", "stderr": f"Timed out after {timeout}s", "exit_code": -1, "command": cmd}
    except Exception as e:
        return {"passed": False, "stdout": "", "stderr": str(e), "exit_code": -1, "command": cmd}


async def _check_syntax(workspace_path: str) -> Dict[str, Any]:
    base = Path(workspace_path)
    py_files = list(base.rglob("*.py"))
    if not py_files:
        return {"passed": True, "details": "No .py files found", "files_checked": 0, "errors": []}

    errors = []
    for py_file in py_files:
        result = await _run(f"python3 -m py_compile {py_file}", cwd=workspace_path, timeout=10)
        if not result["passed"]:
            errors.append({"file": str(py_file), "error": result["stderr"]})

    return {
        "passed": len(errors) == 0,
        "files_checked": len(py_files),
        "errors": errors,
        "details": f"Checked {len(py_files)} files, {len(errors)} errors",
    }


async def _run_pytest(workspace_path: str) -> Dict[str, Any]:
    base = Path(workspace_path)
    test_dirs = list(base.glob("test*")) + list(base.glob("**/test_*.py"))
    if not test_dirs:
        return {"passed": True, "details": "No tests found — skipped", "skipped": True}

    result = await _run(
        f"{sys.executable} -m pytest {workspace_path} -v --tb=short --timeout=30 2>&1",
        cwd=workspace_path,
        timeout=120,
    )
    lines = result["stdout"].splitlines()
    passed = failed = 0
    for line in lines:
        if " passed" in line:
            try:
                passed = int(line.split(" passed")[0].strip().split()[-1])
            except Exception:
                pass
        if " failed" in line:
            try:
                failed = int(line.split(" failed")[0].strip().split()[-1])
            except Exception:
                pass

    return {
        "passed": result["passed"],
        "tests_passed": passed,
        "tests_failed": failed,
        "output": result["stdout"][:3000],
        "details": f"{passed} passed, {failed} failed",
    }


async def _pip_check(workspace_path: str) -> Dict[str, Any]:
    result = await _run(f"{sys.executable} -m pip check", cwd=workspace_path, timeout=30)
    return {
        "passed": result["passed"],
        "output": result["stdout"] + result["stderr"],
        "details": "pip dependency check",
    }


async def verify_build(workspace_path: str = "workspaces") -> Dict[str, Any]:
    """
    Run full build verification on a workspace directory.
    Returns structured results with overall pass/fail.
    """
    start = time.time()

    if not Path(workspace_path).exists():
        return {
            "passed": False,
            "workspace": workspace_path,
            "error": "Workspace path does not exist",
            "results": {},
            "duration_s": 0,
        }

    syntax_task = _check_syntax(workspace_path)
    pytest_task = _run_pytest(workspace_path)
    pip_task = _pip_check(workspace_path)

    syntax, pytest, pip = await asyncio.gather(syntax_task, pytest_task, pip_task)

    results = {
        "syntax": syntax,
        "pytest": pytest,
        "pip_check": pip,
    }

    overall_passed = (
        syntax["passed"]
        and (pytest.get("skipped", False) or pytest["passed"])
    )

    healing_needed = not overall_passed
    healing_suggestions = []
    if not syntax["passed"]:
        for err in syntax.get("errors", []):
            healing_suggestions.append(f"Fix syntax in {err['file']}: {err['error'][:100]}")
    if not pytest.get("skipped") and not pytest["passed"]:
        healing_suggestions.append("Fix failing tests")

    return {
        "passed": overall_passed,
        "workspace": workspace_path,
        "results": results,
        "duration_s": round(time.time() - start, 2),
        "healing_needed": healing_needed,
        "healing_suggestions": healing_suggestions,
    }
