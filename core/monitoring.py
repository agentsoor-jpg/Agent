"""
core/monitoring.py - Production Monitoring Module v7.0
Prometheus metrics, health dashboard, alerts, performance benchmarks.
"""

import asyncio
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ── Metrics Collection ──────────────────────────────────────────────────────────

class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class Metric:
    """Base metric class."""
    
    def __init__(self, name: str, description: str, metric_type: MetricType, labels: Optional[List[str]] = None):
        self.name = name
        self.description = description
        self.metric_type = metric_type
        self.labels = labels or []
        self._value: float = 0
        self._values: Dict[str, float] = defaultdict(float)
        self._histogram_buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
        self._histogram_counts: Dict[str, List[float]] = defaultdict(list)


class MetricsCollector:
    """Collect and store metrics."""
    
    def __init__(self):
        self._metrics: Dict[str, Metric] = {}
        self._lock = asyncio.Lock()
    
    def register(
        self,
        name: str,
        description: str,
        metric_type: MetricType,
        labels: Optional[List[str]] = None
    ):
        """Register a new metric."""
        self._metrics[name] = Metric(name, description, metric_type, labels)
    
    async def increment(self, name: str, value: float = 1, labels: Optional[Dict[str, str]] = None):
        """Increment a counter metric."""
        async with self._lock:
            if name not in self._metrics:
                self.register(name, "", MetricType.COUNTER)
            
            metric = self._metrics[name]
            key = self._labels_to_key(labels)
            
            if metric.metric_type == MetricType.COUNTER:
                metric._values[key] += value
    
    async def set(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge metric value."""
        async with self._lock:
            if name not in self._metrics:
                self.register(name, "", MetricType.GAUGE)
            
            metric = self._metrics[name]
            key = self._labels_to_key(labels)
            metric._values[key] = value
    
    async def observe(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Observe a value for histogram/summary."""
        async with self._lock:
            if name not in self._metrics:
                self.register(name, "", MetricType.HISTOGRAM)
            
            metric = self._metrics[name]
            key = self._labels_to_key(labels)
            
            if metric.metric_type == MetricType.HISTOGRAM:
                metric._histogram_counts[key].append(value)
            else:
                metric._values[key] = value
    
    def _labels_to_key(self, labels: Optional[Dict[str, str]]) -> str:
        if not labels:
            return ""
        return json.dumps(labels, sort_keys=True)
    
    async def get_all(self) -> Dict[str, Any]:
        """Get all metrics in Prometheus format."""
        async with self._lock:
            result = {}
            for name, metric in self._metrics.items():
                result[name] = {
                    "type": metric.metric_type.value,
                    "values": dict(metric._values),
                }
                if metric.metric_type == MetricType.HISTOGRAM:
                    for key, values in metric._histogram_counts.items():
                        if values:
                            sorted_values = sorted(values)
                            result[name][f"histogram_{key}"] = {
                                "count": len(sorted_values),
                                "sum": sum(sorted_values),
                                "mean": sum(sorted_values) / len(sorted_values),
                                "min": min(sorted_values),
                                "max": max(sorted_values),
                                "p50": sorted_values[len(sorted_values) // 2],
                                "p95": sorted_values[int(len(sorted_values) * 0.95)],
                                "p99": sorted_values[int(len(sorted_values) * 0.99)],
                            }
            return result
    
    async def export_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        metrics = await self.get_all()
        lines = []
        
        for name, data in metrics.items():
            lines.append(f"# HELP {name} {data.get('description', '')}")
            lines.append(f"# TYPE {name} {data['type']}")
            
            for key, value in data.get("values", {}).items():
                if key:
                    labels = json.loads(key)
                    label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
                    lines.append(f"{name}{{{label_str}}} {value}")
                else:
                    lines.append(f"{name} {value}")
        
        return "\n".join(lines)


# ── Prometheus Endpoint ─────────────────────────────────────────────────────────

class PrometheusExporter:
    """Prometheus metrics endpoint."""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
    
    async def get_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        return await self.collector.export_prometheus()
    
    async def get_json(self) -> Dict[str, Any]:
        """Get metrics as JSON."""
        return await self.collector.get_all()


# ── Alert System ────────────────────────────────────────────────────────────────

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Alert:
    """Represents an alert."""
    
    def __init__(
        self,
        name: str,
        level: AlertLevel,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.level = level
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc)
        self.fired = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "level": self.level.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "fired": self.fired,
        }


class AlertRule:
    """Alert rule definition."""
    
    def __init__(
        self,
        name: str,
        condition: Callable[[], bool],
        level: AlertLevel,
        message: str,
        cooldown_seconds: int = 300
    ):
        self.name = name
        self.condition = condition
        self.level = level
        self.message = message
        self.cooldown_seconds = cooldown_seconds
        self._last_fired: Optional[float] = None
    
    def should_fire(self) -> bool:
        if self._last_fired is not None:
            if time.time() - self._last_fired < self.cooldown_seconds:
                return False
        
        try:
            if self.condition():
                self._last_fired = time.time()
                return True
        except Exception:
            pass
        
        return False


class AlertManager:
    """Manage alerts and notifications."""
    
    def __init__(self):
        self._rules: List[AlertRule] = []
        self._active_alerts: Dict[str, Alert] = {}
        self._webhook_urls: Dict[str, str] = {}
        self._email_recipients: List[str] = []
        self._lock = asyncio.Lock()
    
    def add_rule(
        self,
        name: str,
        condition: Callable[[], bool],
        level: AlertLevel,
        message: str,
        cooldown_seconds: int = 300
    ):
        """Add an alert rule."""
        rule = AlertRule(name, condition, level, message, cooldown_seconds)
        self._rules.append(rule)
    
    def register_webhook(self, name: str, url: str):
        """Register a webhook for alerts."""
        self._webhook_urls[name] = url
    
    def register_email(self, email: str):
        """Register an email for alerts."""
        self._email_recipients.append(email)
    
    async def check_rules(self) -> List[Alert]:
        """Check all rules and fire alerts."""
        async with self._lock:
            fired_alerts = []
            
            for rule in self._rules:
                if rule.should_fire():
                    alert = Alert(
                        rule.name,
                        rule.level,
                        rule.message,
                        {"rule": rule.name}
                    )
                    alert.fired = True
                    self._active_alerts[rule.name] = alert
                    fired_alerts.append(alert)
                    
                    # Send notifications
                    await self._send_notifications(alert)
            
            return fired_alerts
    
    async def _send_notifications(self, alert: Alert):
        """Send alert notifications."""
        for name, url in self._webhook_urls.items():
            try:
                await self._send_webhook(url, alert)
            except Exception as e:
                print(f"Failed to send alert webhook: {e}")
    
    async def _send_webhook(self, url: str, alert: Alert):
        """Send alert to webhook."""
        import httpx
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json=alert.to_dict())
    
    async def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all active alerts."""
        return [a.to_dict() for a in self._active_alerts.values()]
    
    async def resolve_alert(self, name: str):
        """Resolve an alert."""
        async with self._lock:
            if name in self._active_alerts:
                del self._active_alerts[name]


# ── Performance Benchmarks ─────────────────────────────────────────────────────

class PerformanceMonitor:
    """Monitor and track performance metrics."""
    
    def __init__(self):
        self._benchmarks: Dict[str, List[float]] = defaultdict(list)
        self._start_times: Dict[str, float] = {}
        self._lock = asyncio.Lock()
    
    def start(self, name: str):
        """Start timing a benchmark."""
        self._start_times[name] = time.time()
    
    def end(self, name: str):
        """End timing and record result."""
        if name in self._start_times:
            duration = time.time() - self._start_times[name]
            self._benchmarks[name].append(duration)
            del self._start_times[name]
            
            # Keep only last 1000 samples
            if len(self._benchmarks[name]) > 1000:
                self._benchmarks[name] = self._benchmarks[name][-1000:]
    
    async def get_stats(self, name: str) -> Optional[Dict[str, float]]:
        """Get statistics for a benchmark."""
        async with self._lock:
            if name not in self._benchmarks or not self._benchmarks[name]:
                return None
            
            values = sorted(self._benchmarks[name])
            n = len(values)
            
            return {
                "count": n,
                "mean": sum(values) / n,
                "min": min(values),
                "max": max(values),
                "p50": values[n // 2],
                "p95": values[int(n * 0.95)],
                "p99": values[int(n * 0.99)],
            }
    
    async def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """Get stats for all benchmarks."""
        async with self._lock:
            return {
                name: await self.get_stats(name) or {}
                for name in self._benchmarks.keys()
            }


# ── Uptime Tracking ────────────────────────────────────────────────────────────

class UptimeTracker:
    """Track system uptime."""
    
    def __init__(self):
        self._start_time = time.time()
        self._downtimes: List[Dict[str, Any]] = []
        self._current_downtime: Optional[Dict[str, Any]] = None
        self._lock = asyncio.Lock()
    
    async def mark_down(self, reason: str = ""):
        """Mark system as down."""
        async with self._lock:
            if self._current_downtime is None:
                self._current_downtime = {
                    "start": time.time(),
                    "reason": reason,
                }
    
    async def mark_up(self):
        """Mark system as up."""
        async with self._lock:
            if self._current_downtime:
                self._current_downtime["end"] = time.time()
                self._downtimes.append(self._current_downtime)
                self._current_downtime = None
    
    async def get_uptime_stats(self) -> Dict[str, Any]:
        """Get uptime statistics."""
        async with self._lock:
            uptime = time.time() - self._start_time
            total_downtime = sum(
                d.get("end", time.time()) - d["start"]
                for d in self._downtimes
            )
            
            if self._current_downtime:
                total_downtime += time.time() - self._current_downtime["start"]
            
            uptime_percent = (
                (uptime - total_downtime) / uptime * 100
                if uptime > 0 else 100
            )
            
            return {
                "uptime_seconds": uptime,
                "uptime_hours": uptime / 3600,
                "uptime_percent": round(uptime_percent, 2),
                "total_downtime_seconds": total_downtime,
                "downtime_count": len(self._downtimes) + (1 if self._current_downtime else 0),
                "currently_down": self._current_downtime is not None,
                "started_at": datetime.fromtimestamp(
                    self._start_time, tz=timezone.utc
                ).isoformat(),
            }


# ── Health Dashboard ───────────────────────────────────────────────────────────

class HealthDashboard:
    """Generate health dashboard JSON."""
    
    def __init__(
        self,
        collector: MetricsCollector,
        alert_manager: AlertManager,
        uptime_tracker: UptimeTracker
    ):
        self.collector = collector
        self.alert_manager = alert_manager
        self.uptime_tracker = uptime_tracker
    
    async def get_dashboard(self) -> Dict[str, Any]:
        """Generate complete health dashboard."""
        uptime_stats = await self.uptime_tracker.get_uptime_stats()
        active_alerts = await self.alert_manager.get_active_alerts()
        metrics = await self.collector.get_all()
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "7.0.0",
            "uptime": uptime_stats,
            "alerts": {
                "active": active_alerts,
                "count": len(active_alerts),
            },
            "metrics": metrics,
            "status": self._calculate_status(active_alerts, uptime_stats),
        }
    
    def _calculate_status(self, alerts: List[Dict], uptime: Dict) -> str:
        if uptime.get("currently_down"):
            return "DOWN"
        
        for alert in alerts:
            if alert.get("level") in ("error", "critical"):
                return "DEGRADED"
        
        return "HEALTHY"


# ── Global instances ───────────────────────────────────────────────────────────

metrics_collector = MetricsCollector()
prometheus_exporter = PrometheusExporter(metrics_collector)
alert_manager = AlertManager()
performance_monitor = PerformanceMonitor()
uptime_tracker = UptimeTracker()
health_dashboard = HealthDashboard(
    metrics_collector,
    alert_manager,
    uptime_tracker
)
