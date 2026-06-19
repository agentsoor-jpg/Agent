"""Context Engine - محرك السياق"""
from typing import Dict, List

class ContextEngine:
    def __init__(self, max_files: int = 20, max_tokens: int = 50000):
        self.max_files = max_files
        self.max_tokens = max_tokens
    async def compile(self, files: dict, history: list = None, environment: dict = None) -> dict:
        selected = dict(list(files.items())[:self.max_files])
        return {"files": selected, "history": (history or [])[-10:], "environment": environment or {}}
    async def compress(self, context: dict) -> dict:
        return context
    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4
