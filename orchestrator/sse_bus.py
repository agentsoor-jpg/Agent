"""
SSE event bus — shared singleton for publishing and subscribing to workflow events.
Imported by both main.py (subscriber) and dispatcher.py (publisher).
"""

import asyncio
import json
import time
from typing import Dict, List, Optional

# workflow_id → list of asyncio.Queue subscribers
_subscribers: Dict[str, List[asyncio.Queue]] = {}


def subscribe(workflow_id: str) -> asyncio.Queue:
    """Create and register a new queue for this workflow. Returns the queue."""
    q: asyncio.Queue = asyncio.Queue()
    if workflow_id not in _subscribers:
        _subscribers[workflow_id] = []
    _subscribers[workflow_id].append(q)
    return q


def unsubscribe(workflow_id: str, q: asyncio.Queue):
    """Remove a subscriber queue."""
    try:
        _subscribers.get(workflow_id, []).remove(q)
    except ValueError:
        pass


def publish(workflow_id: str, event_type: str, data: dict):
    """
    Publish an event to all SSE subscribers for this workflow.
    Safe to call from sync or async context.
    """
    event = {
        "event": event_type,
        "workflow_id": workflow_id,
        "timestamp": time.time(),
        "data": data,
    }
    for q in list(_subscribers.get(workflow_id, [])):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


def close(workflow_id: str):
    """Send sentinel None to all subscribers so they stop iterating."""
    for q in list(_subscribers.get(workflow_id, [])):
        try:
            q.put_nowait(None)
        except Exception:
            pass
    _subscribers.pop(workflow_id, None)


def format_sse(event: dict) -> str:
    """Format a dict as an SSE message string."""
    etype = event.get("event", "message")
    payload = json.dumps(event)
    return f"event: {etype}\ndata: {payload}\n\n"
