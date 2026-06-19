"""Provider Manager"""
from reasoning.claude_adapter import ClaudeAdapter
from reasoning.gemini_adapter import GeminiAdapter
class ProviderManager:
    def __init__(self): self.providers={"claude":ClaudeAdapter(),"gemini":GeminiAdapter()}
    async def think(self, prompt, provider="claude"): return await self.providers[provider].think(prompt)
