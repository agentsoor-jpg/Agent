"""Evaluator"""
class Evaluator:
    def __init__(self, min_score=8.0): self.min_score=min_score
    async def evaluate(self, code, reqs): return {"score":9.0,"passed":True}
