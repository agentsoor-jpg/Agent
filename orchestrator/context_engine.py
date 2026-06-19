"""Context Engine - Compile and compress context for agents"""
from typing import Dict, List, Optional


class ContextEngine:
    def __init__(self, max_files: int = 20, max_tokens: int = 50000):
        self.max_files = max_files
        self.max_tokens = max_tokens

    async def compile(
        self,
        files: dict,
        history: Optional[List] = None,
        environment: Optional[dict] = None,
    ) -> dict:
        selected = dict(list(files.items())[: self.max_files])
        return {
            "files": selected,
            "history": (history or [])[-10:],
            "environment": environment or {},
            "token_estimate": self.estimate_tokens(str(selected)),
        }

    async def compress(self, context: dict, target_tokens: int = 20000) -> dict:
        """Trim context to fit within target token budget."""
        files = context.get("files", {})
        trimmed: Dict[str, str] = {}
        total = 0
        budget = target_tokens * 4  # chars per token ~4

        for path, content in files.items():
            chars = len(str(content))
            if total + chars > budget:
                break
            trimmed[path] = content
            total += chars

        return {
            **context,
            "files": trimmed,
            "_compressed": len(trimmed) < len(files),
            "_files_dropped": len(files) - len(trimmed),
        }

    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4
