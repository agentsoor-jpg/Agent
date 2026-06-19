"""Gemini Adapter"""
import httpx
class GeminiAdapter:
    def __init__(self): self.endpoint="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    async def think(self, prompt): return {"success":True,"content":"Gemini response"}
