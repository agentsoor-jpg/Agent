"""
Permanent project memory — ChromaDB-compatible API backed by JSON files + TF-IDF similarity.
ChromaDB is not available in this environment, so we use a pure-Python implementation
that persists to memory/data/ and provides the same interface.
"""

import json
import math
import os
import re
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

MEMORY_DIR = Path("memory/data")
PROJECTS_FILE = MEMORY_DIR / "projects.json"
PREFERENCES_FILE = MEMORY_DIR / "preferences.json"


# ── Persistence helpers ─────────────────────────────────────────────────────


def _ensure_dir():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def _load_projects() -> Dict[str, dict]:
    _ensure_dir()
    if PROJECTS_FILE.exists():
        try:
            return json.loads(PROJECTS_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_projects(projects: Dict[str, dict]):
    _ensure_dir()
    PROJECTS_FILE.write_text(json.dumps(projects, indent=2, default=str))


def _load_preferences() -> dict:
    _ensure_dir()
    if PREFERENCES_FILE.exists():
        try:
            return json.loads(PREFERENCES_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_preferences(prefs: dict):
    _ensure_dir()
    PREFERENCES_FILE.write_text(json.dumps(prefs, indent=2, default=str))


# ── TF-IDF similarity ───────────────────────────────────────────────────────


def _tokenize(text: str) -> List[str]:
    return re.findall(r"\b\w+\b", text.lower())


def _tf(tokens: List[str]) -> Dict[str, float]:
    counts = Counter(tokens)
    total = len(tokens) or 1
    return {w: c / total for w, c in counts.items()}


def _idf(word: str, docs: List[List[str]]) -> float:
    n = len(docs) or 1
    df = sum(1 for d in docs if word in d)
    return math.log((n + 1) / (df + 1)) + 1


def _tfidf_vector(tokens: List[str], vocab: List[str], idf_cache: Dict[str, float]) -> Dict[str, float]:
    tf = _tf(tokens)
    return {w: tf.get(w, 0) * idf_cache.get(w, 1) for w in vocab}


def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    keys = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in keys)
    mag_a = math.sqrt(sum(v ** 2 for v in a.values()))
    mag_b = math.sqrt(sum(v ** 2 for v in b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _similarity_search(query: str, projects: Dict[str, dict], top_k: int = 5) -> List[dict]:
    if not projects:
        return []

    def project_text(p: dict) -> str:
        return " ".join([
            p.get("name", ""),
            p.get("description", ""),
            " ".join(p.get("decisions", [])),
            " ".join(p.get("patterns", [])),
            p.get("architecture", ""),
        ])

    docs = {pid: _tokenize(project_text(p)) for pid, p in projects.items()}
    vocab = list({w for tokens in docs.values() for w in tokens})
    idf_cache = {w: _idf(w, list(docs.values())) for w in vocab}

    query_tokens = _tokenize(query)
    query_vec = _tfidf_vector(query_tokens, vocab, idf_cache)

    scored = []
    for pid, tokens in docs.items():
        doc_vec = _tfidf_vector(tokens, vocab, idf_cache)
        score = _cosine(query_vec, doc_vec)
        scored.append((score, pid))

    scored.sort(reverse=True)
    result = []
    for score, pid in scored[:top_k]:
        if score > 0:
            p = dict(projects[pid])
            p["_similarity_score"] = round(score, 4)
            result.append(p)
    return result


# ── Public API ──────────────────────────────────────────────────────────────


def store_project(project_data: dict) -> str:
    """
    Save a project to permanent memory.

    Required fields: name, description
    Optional: architecture, decisions (list), files (dict), patterns (list), stack (list)

    Returns: project_id
    """
    projects = _load_projects()
    project_id = project_data.get("id") or str(uuid.uuid4())
    projects[project_id] = {
        "id": project_id,
        "name": project_data.get("name", "Unnamed Project"),
        "description": project_data.get("description", ""),
        "architecture": project_data.get("architecture", ""),
        "decisions": project_data.get("decisions", []),
        "files": project_data.get("files", {}),
        "patterns": project_data.get("patterns", []),
        "stack": project_data.get("stack", []),
        "workflow_id": project_data.get("workflow_id", ""),
        "complexity": project_data.get("complexity", "medium"),
        "created_at": project_data.get("created_at", time.time()),
        "updated_at": time.time(),
    }
    _save_projects(projects)
    return project_id


def search_similar(query: str, top_k: int = 5) -> List[dict]:
    """
    Search for past projects similar to the query string.
    Returns up to top_k projects sorted by similarity score.
    """
    projects = _load_projects()
    return _similarity_search(query, projects, top_k)


def get_project_context(project_id: str) -> Optional[dict]:
    """Return full project record by ID, or None if not found."""
    projects = _load_projects()
    return projects.get(project_id)


def update_project(project_id: str, updates: dict) -> Optional[dict]:
    """
    Append/update fields on an existing project.
    Lists (decisions, patterns) are appended, not replaced.
    """
    projects = _load_projects()
    if project_id not in projects:
        return None

    p = projects[project_id]

    for key in ("decisions", "patterns"):
        if key in updates:
            existing = p.get(key, [])
            new_items = updates.pop(key, [])
            p[key] = list(set(existing + new_items))

    if "files" in updates:
        p["files"] = {**p.get("files", {}), **updates.pop("files")}

    p.update(updates)
    p["updated_at"] = time.time()
    projects[project_id] = p
    _save_projects(projects)
    return p


def list_all_projects() -> List[dict]:
    """Return all stored projects sorted by updated_at descending."""
    projects = _load_projects()
    items = list(projects.values())
    items.sort(key=lambda p: p.get("updated_at", 0), reverse=True)
    return items


def get_user_preferences() -> dict:
    return _load_preferences()


def update_user_preferences(updates: dict) -> dict:
    prefs = _load_preferences()
    prefs.update(updates)
    _save_preferences(prefs)
    return prefs


def load_context_for_workflow(requirements: str) -> dict:
    """
    Called at the start of a new workflow.
    Returns: {similar_projects, preferences, patterns}
    """
    similar = search_similar(requirements, top_k=3)
    prefs = get_user_preferences()

    # Aggregate patterns from similar projects
    patterns: List[str] = []
    for p in similar:
        patterns += p.get("patterns", [])

    return {
        "similar_projects": similar,
        "preferences": prefs,
        "common_patterns": list(set(patterns))[:20],
        "loaded_at": time.time(),
    }
