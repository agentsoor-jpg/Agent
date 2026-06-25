"""Base agent utilities and adapter interfaces."""
import os
import json
from loguru import logger

class AgentAdapter:
    def __init__(self, name: str, base_url: str = None):
        self.name = name
        self.base_url = base_url or os.getenv(f"AGENT_{name.upper()}_URL")

    def call(self, payload: dict) -> dict:
        """Override in concrete adapters: call remote API or run local logic."""
        raise NotImplementedError
