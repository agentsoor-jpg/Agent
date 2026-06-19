"""
In-process project context manager.
Tracks file purposes, summarizes when context exceeds token limits,
and returns only the relevant context for a given task.
"""

import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

TOKEN_LIMIT = 30000  # rough char limit for safe context size
SUMMARY_RATIO = 0.3  # keep 30% of content when summarizing


# ── Summarizer ──────────────────────────────────────────────────────────────


def _summarize_content(content: str, max_chars: int = 500) -> str:
    """Keep first max_chars chars and add ellipsis."""
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + f"\n... [{len(content) - max_chars} chars truncated]"


def _summarize_file(file_path: str, content: str, purpose: str) -> dict:
    return {
        "path": file_path,
        "purpose": purpose,
        "lines": content.count("\n"),
        "chars": len(content),
        "summary": _summarize_content(content, 200),
        "summarized": True,
    }


# ── Context manager ─────────────────────────────────────────────────────────


class ProjectContext:
    """Maintains full project state in memory for a single workflow session."""

    def __init__(self, workflow_id: str, requirements: str = ""):
        self.workflow_id = workflow_id
        self.requirements = requirements
        self.files: Dict[str, dict] = {}  # path → {content, purpose, added_at}
        self.decisions: List[dict] = []
        self.errors: List[dict] = []
        self.phases_completed: List[str] = []
        self.created_at = time.time()
        self.updated_at = time.time()
        self._summarized = False

    def add_file(self, file_path: str, content: str, purpose: str = ""):
        """Add or update a file in the context."""
        self.files[file_path] = {
            "path": file_path,
            "content": content,
            "purpose": purpose or f"File: {file_path}",
            "lines": content.count("\n"),
            "chars": len(content),
            "summarized": False,
            "added_at": time.time(),
        }
        self.updated_at = time.time()
        self._auto_trim()

    def add_decision(self, decision: str, rationale: str = ""):
        self.decisions.append({"decision": decision, "rationale": rationale, "at": time.time()})

    def add_error(self, phase: str, error: str, resolved: bool = False):
        self.errors.append({"phase": phase, "error": error, "resolved": resolved, "at": time.time()})

    def mark_phase_complete(self, phase_name: str):
        if phase_name not in self.phases_completed:
            self.phases_completed.append(phase_name)

    def _total_chars(self) -> int:
        return sum(f["chars"] for f in self.files.values())

    def _auto_trim(self):
        """Auto-summarize when context exceeds token limit."""
        if self._total_chars() > TOKEN_LIMIT and not self._summarized:
            self._summarize_all()

    def _summarize_all(self):
        """Replace file contents with summaries."""
        for path, file_info in self.files.items():
            if not file_info.get("summarized"):
                file_info["summary"] = _summarize_content(file_info["content"], 300)
                file_info["content"] = ""  # free memory
                file_info["summarized"] = True
        self._summarized = True

    def get_relevant_context(self, task_description: str) -> dict:
        """
        Return only files relevant to the given task.
        Uses keyword matching to score relevance.
        """
        keywords = set(re.findall(r"\b\w{3,}\b", task_description.lower()))

        scored_files = []
        for path, file_info in self.files.items():
            text = (path + " " + file_info.get("purpose", "")).lower()
            score = sum(1 for kw in keywords if kw in text)
            scored_files.append((score, path, file_info))

        scored_files.sort(reverse=True)

        # Take top files up to half the token limit
        selected = {}
        total = 0
        for score, path, info in scored_files:
            content = info.get("content") or info.get("summary", "")
            if total + len(content) > TOKEN_LIMIT // 2:
                selected[path] = _summarize_content(content, 150)
            else:
                selected[path] = content
                total += len(content)

        return {
            "workflow_id": self.workflow_id,
            "requirements": self.requirements,
            "files": selected,
            "decisions": self.decisions[-10:],
            "phases_completed": self.phases_completed,
            "errors": [e for e in self.errors if not e["resolved"]][-5:],
            "task": task_description,
        }

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "requirements": self.requirements,
            "file_count": len(self.files),
            "files_summary": {
                path: {
                    "purpose": info["purpose"],
                    "lines": info["lines"],
                    "summarized": info.get("summarized", False),
                }
                for path, info in self.files.items()
            },
            "decisions": self.decisions,
            "phases_completed": self.phases_completed,
            "errors": self.errors,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "summarized": self._summarized,
        }


# ── Global context registry ─────────────────────────────────────────────────

_contexts: Dict[str, ProjectContext] = {}


def get_context(workflow_id: str) -> Optional[ProjectContext]:
    return _contexts.get(workflow_id)


def create_context(workflow_id: str, requirements: str = "") -> ProjectContext:
    ctx = ProjectContext(workflow_id, requirements)
    _contexts[workflow_id] = ctx
    return ctx


def drop_context(workflow_id: str):
    _contexts.pop(workflow_id, None)


def list_contexts() -> List[dict]:
    return [ctx.to_dict() for ctx in _contexts.values()]
