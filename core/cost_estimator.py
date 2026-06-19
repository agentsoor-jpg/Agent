"""
core/cost_estimator.py - AI Cost Estimation v7.1
Model pricing, task cost estimation, budget tracking.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# Model pricing per 1M tokens (input/output)
MODEL_PRICING = {
    "claude-3-opus": {"input": 15.00, "output": 75.00},
    "claude-3-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "gemini-pro": {"input": 0.125, "output": 0.375},
    "gemini-ultra": {"input": 1.25, "output": 5.00},
    "local-llama": {"input": 0.00, "output": 0.00},  # Free for local models
}


class CostEstimator:
    """Estimate and track AI costs."""
    
    def __init__(self, storage_file: str = "state/cost_tracking.json"):
        self.storage_file = Path(storage_file)
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        
        self._data: Dict[str, Any] = {
            "tasks": {},
            "projects": {},
            "daily": {},
            "budgets": {},
        }
        self._load()
    
    def _load(self):
        """Load cost data from storage."""
        if self.storage_file.exists():
            try:
                self._data = json.loads(self.storage_file.read_text())
            except (json.JSONDecodeError, IOError):
                pass
    
    def _save(self):
        """Persist cost data."""
        try:
            self.storage_file.write_text(json.dumps(self._data, indent=2, default=str))
        except IOError:
            pass
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough approximation)."""
        # ~4 chars per token for English
        return len(text) // 4
    
    def estimate_cost(
        self,
        task_description: str,
        agent_type: str = "openhands",
        model: str = "gpt-3.5-turbo"
    ) -> Dict[str, Any]:
        """
        Estimate cost for a task.
        
        Returns breakdown of estimated tokens and cost.
        """
        desc_tokens = self.estimate_tokens(task_description)
        
        # Estimate based on task complexity
        complexity_multipliers = {
            "simple": 1.0,      # Fix, rename, format
            "medium": 3.0,      # CRUD, refactor
            "complex": 10.0,    # Architecture, full apps
            "huge": 50.0,       # Large systems
        }
        
        # Determine complexity
        simple_keywords = ["fix", "rename", "format", "lint", "typo"]
        complex_keywords = ["architecture", "redesign", "migrate", "integrate"]
        
        if any(k in task_description.lower() for k in complex_keywords):
            complexity = "complex"
            multiplier = complexity_multipliers["complex"]
        elif any(k in task_description.lower() for k in simple_keywords):
            complexity = "simple"
            multiplier = complexity_multipliers["simple"]
        else:
            complexity = "medium"
            multiplier = complexity_multipliers["medium"]
        
        # Agent-specific multipliers
        agent_multipliers = {
            "openhands": 2.0,   # More thorough analysis
            "aider": 1.5,       # Targeted edits
            "bolt": 1.2,         # Quick scaffolding
            "replit": 1.0,       # Light testing
        }
        
        agent_mult = agent_multipliers.get(agent_type, 1.0)
        
        # Calculate estimates
        estimated_tokens = int(desc_tokens * multiplier * agent_mult * 10)  # 10x for full task
        estimated_cost = self._calculate_cost(estimated_tokens, model)
        
        return {
            "task_description": task_description[:100],
            "complexity": complexity,
            "agent_type": agent_type,
            "model": model,
            "estimated_tokens": estimated_tokens,
            "estimated_input_cost": estimated_cost["input_cost"],
            "estimated_output_cost": estimated_cost["output_cost"],
            "estimated_total_cost": estimated_cost["total_cost"],
            "pricing_used": MODEL_PRICING.get(model, MODEL_PRICING["gpt-3.5-turbo"]),
        }
    
    def _calculate_cost(self, tokens: int, model: str) -> Dict[str, float]:
        """Calculate cost for tokens."""
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["gpt-3.5-turbo"])
        
        # Assume 30% input, 70% output
        input_tokens = int(tokens * 0.3)
        output_tokens = int(tokens * 0.7)
        
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        
        return {
            "input_cost": round(input_cost, 6),
            "output_cost": round(output_cost, 6),
            "total_cost": round(input_cost + output_cost, 6),
        }
    
    def track_actual_cost(
        self,
        task_id: str,
        input_tokens: int,
        output_tokens: int,
        model: str,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Track actual cost after task completion."""
        cost = self._calculate_cost(input_tokens + output_tokens, model)
        
        record = {
            "task_id": task_id,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "input_cost": cost["input_cost"],
            "output_cost": cost["output_cost"],
            "total_cost": cost["total_cost"],
            "project_id": project_id,
            "tracked_at": datetime.now(timezone.utc).isoformat(),
        }
        
        self._data["tasks"][task_id] = record
        
        # Add to project total
        if project_id:
            if project_id not in self._data["projects"]:
                self._data["projects"][project_id] = {
                    "total_cost": 0,
                    "tasks": [],
                }
            
            self._data["projects"][project_id]["tasks"].append(task_id)
            self._data["projects"][project_id]["total_cost"] += cost["total_cost"]
        
        # Add to daily totals
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today not in self._data["daily"]:
            self._data["daily"][today] = {"total": 0, "tasks": []}
        
        self._data["daily"][today]["tasks"].append(task_id)
        self._data["daily"][today]["total"] += cost["total_cost"]
        
        self._save()
        
        return record
    
    def get_project_cost(self, project_id: str) -> Dict[str, Any]:
        """Get cost breakdown for a project."""
        if project_id not in self._data["projects"]:
            return {
                "project_id": project_id,
                "total_cost": 0,
                "task_count": 0,
                "breakdown": {},
            }
        
        project = self._data["projects"][project_id]
        task_ids = project.get("tasks", [])
        
        breakdown = {"by_model": {}, "by_agent": {}}
        total = 0
        
        for task_id in task_ids:
            if task_id in self._data["tasks"]:
                task = self._data["tasks"][task_id]
                model = task.get("model", "unknown")
                breakdown["by_model"][model] = breakdown["by_model"].get(model, 0) + task["total_cost"]
                total += task["total_cost"]
        
        return {
            "project_id": project_id,
            "total_cost": total,
            "task_count": len(task_ids),
            "breakdown": breakdown,
        }
    
    def get_daily_costs(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get daily cost summary for last N days."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        costs = []
        
        for i in range(days):
            date = (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)).timestamp() - (i * 86400)
            date_str = datetime.fromtimestamp(date, tz=timezone.utc).strftime("%Y-%m-%d")
            
            if date_str in self._data["daily"]:
                day_data = self._data["daily"][date_str]
                costs.append({
                    "date": date_str,
                    "total": day_data.get("total", 0),
                    "task_count": len(day_data.get("tasks", [])),
                })
            else:
                costs.append({
                    "date": date_str,
                    "total": 0,
                    "task_count": 0,
                })
        
        return list(reversed(costs))
    
    def budget_alert(self, project_id: str, max_budget: float) -> Dict[str, Any]:
        """Check if project is exceeding budget."""
        project_cost = self.get_project_cost(project_id)
        total = project_cost.get("total_cost", 0)
        
        percentage = (total / max_budget * 100) if max_budget > 0 else 0
        
        return {
            "project_id": project_id,
            "max_budget": max_budget,
            "current_cost": total,
            "remaining": max_budget - total,
            "percentage_used": round(percentage, 1),
            "over_budget": total > max_budget,
            "alert": percentage > 80,
            "severity": "critical" if percentage > 100 else "high" if percentage > 80 else "normal",
        }
    
    def set_budget(self, project_id: str, max_budget: float, period: str = "project"):
        """Set budget limit for a project."""
        if project_id not in self._data["budgets"]:
            self._data["budgets"][project_id] = {}
        
        self._data["budgets"][project_id] = {
            "max_budget": max_budget,
            "period": period,
            "set_at": datetime.now(timezone.utc).isoformat(),
        }
        
        self._save()
    
    def compare_estimate_vs_actual(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Compare estimated vs actual cost for a task."""
        if task_id not in self._data["tasks"]:
            return None
        
        actual = self._data["tasks"][task_id]
        
        return {
            "task_id": task_id,
            "actual_cost": actual["total_cost"],
            "model_used": actual["model"],
            "tokens_used": actual["input_tokens"] + actual["output_tokens"],
        }
    
    def get_monthly_report(self, year: int = None, month: int = None) -> Dict[str, Any]:
        """Generate monthly cost report."""
        if year is None:
            now = datetime.now(timezone.utc)
            year = now.year
            month = now.month
        
        month_str = f"{year}-{month:02d}"
        
        total = 0
        tasks = []
        
        for date_str, data in self._data["daily"].items():
            if date_str.startswith(month_str):
                total += data.get("total", 0)
                tasks.extend(data.get("tasks", []))
        
        return {
            "year": year,
            "month": month,
            "total_cost": total,
            "task_count": len(tasks),
            "average_cost_per_task": total / len(tasks) if tasks else 0,
        }
    
    def get_all_models(self) -> List[str]:
        """Get list of all available models with pricing."""
        return [
            {
                "model": model,
                "input_cost_per_1m": pricing["input"],
                "output_cost_per_1m": pricing["output"],
            }
            for model, pricing in MODEL_PRICING.items()
        ]


# Global instance
cost_estimator = CostEstimator()
