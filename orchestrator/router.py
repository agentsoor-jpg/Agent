"""Router: resolve agent names to URLs using environment variables."""
import os

class Router:
    """Simple router that reads agent URLs from environment variables.
    Convention: AGENT_{NAME}_URL, e.g., AGENT_PLANNER_URL
    """
    def __init__(self):
        pass

    def get_agent_url(self, agent_name: str) -> str:
        key = f"AGENT_{agent_name.upper()}_URL"
        url = os.getenv(key)
        if url:
            return url
        # Fallback to OPENHANDS_URL/service-name pattern
        base = os.getenv("OPENHANDS_URL")
        if base:
            return f"{base.rstrip('/')}/{agent_name}"
        return f"http://localhost:{self._get_default_port(agent_name)}/execute"

    def select_agent(self, action: str) -> str:
        """Map a plan action/step to the best-suited agent name."""
        action_lower = action.lower()
        if "frontend" in action_lower or "ui" in action_lower or "html" in action_lower or "css" in action_lower:
            return "bolt"
        elif "test" in action_lower or "verify" in action_lower or "assert" in action_lower or "sandbox" in action_lower:
            return "replit"
        elif "backend" in action_lower or "database" in action_lower or "refactor" in action_lower or "write_file" in action_lower or "update_file" in action_lower:
            return "aider"
        else:
            return "openhands"

    def _get_default_port(self, agent_name: str) -> int:
        mapping = {
            "openhands": 3001,
            "aider": 3002,
            "bolt": 3003,
            "replit": 3004
        }
        return mapping.get(agent_name.lower(), 3001)
