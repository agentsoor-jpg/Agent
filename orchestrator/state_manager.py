"""State Manager - In-memory state with disk backup"""
import json
import time
from pathlib import Path
from typing import Dict, Optional

STATE_DIR = Path("state")


class StateManager:
    def __init__(self):
        self.states: Dict[str, dict] = {}
        STATE_DIR.mkdir(exist_ok=True)

    async def save(self, key: str, state: dict):
        state["_timestamp"] = time.time()
        self.states[key] = state
        self._persist(key, state)

    async def load(self, key: str) -> Optional[dict]:
        if key in self.states:
            return self.states[key]
        return self._restore(key)

    async def delete(self, key: str):
        self.states.pop(key, None)
        path = STATE_DIR / f"{key}.json"
        if path.exists():
            path.unlink()

    async def exists(self, key: str) -> bool:
        return key in self.states or (STATE_DIR / f"{key}.json").exists()

    def list_keys(self) -> list:
        return list(self.states.keys())

    def _persist(self, key: str, state: dict):
        try:
            path = STATE_DIR / f"{key.replace('/', '_')}.json"
            path.write_text(json.dumps(state, indent=2, default=str))
        except Exception:
            pass

    def _restore(self, key: str) -> Optional[dict]:
        try:
            path = STATE_DIR / f"{key.replace('/', '_')}.json"
            if path.exists():
                data = json.loads(path.read_text())
                self.states[key] = data
                return data
        except Exception:
            pass
        return None
