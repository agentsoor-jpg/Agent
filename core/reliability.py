"""
core/reliability.py - Production Reliability Module v7.0
Circuit breaker, graceful degradation, backup/restore, migrations.
"""

import asyncio
import json
import os
import shutil
import signal
import subprocess
import time
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# ── Circuit Breaker ─────────────────────────────────────────────────────────────

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"         # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker pattern to stop calling failing services.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, requests are rejected immediately
    - HALF_OPEN: Testing if service recovered, limited requests pass through
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
        excluded_exceptions: Optional[List[type]] = None
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.excluded_exceptions = excluded_exceptions or []
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitState:
        return self._state
    
    @property
    def failure_count(self) -> int:
        return self._failure_count
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function through the circuit breaker."""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                else:
                    raise CircuitOpenError(
                        f"Circuit breaker is OPEN. Service unavailable. "
                        f"Retry after {self._get_retry_after():.0f}s"
                    )
            
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitOpenError(
                        "Circuit breaker is HALF_OPEN. Max test calls reached."
                    )
                self._half_open_calls += 1
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            await self._on_success()
            return result
            
        except Exception as e:
            if not self._should_exclude(e):
                await self._on_failure()
            raise
    
    def _should_exclude(self, exception: Exception) -> bool:
        return any(isinstance(exception, exc_type) for exc_type in self.excluded_exceptions)
    
    def _should_attempt_reset(self) -> bool:
        if self._last_failure_time is None:
            return True
        return time.time() - self._last_failure_time >= self.recovery_timeout
    
    def _get_retry_after(self) -> float:
        if self._last_failure_time is None:
            return 0
        elapsed = time.time() - self._last_failure_time
        return max(0, self.recovery_timeout - elapsed)
    
    async def _on_success(self):
        async with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED
    
    async def _on_failure(self):
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
    
    async def reset(self):
        """Manually reset the circuit breaker."""
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    def __init__(self, message: str = "Circuit breaker is open"):
        self.retry_after = 60
        super().__init__(message)


# ── Health Checks ──────────────────────────────────────────────────────────────

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheck:
    """Health check system with auto-restart capability."""
    
    def __init__(self, name: str, check_func: Callable, threshold: int = 3):
        self.name = name
        self.check_func = check_func
        self.threshold = threshold
        self._failure_count = 0
        self._last_check_time: Optional[float] = None
        self._last_status: Optional[HealthStatus] = None
        self._lock = asyncio.Lock()
    
    async def check(self) -> Tuple[HealthStatus, Dict[str, Any]]:
        """Run the health check."""
        async with self._lock:
            try:
                if asyncio.iscoroutinefunction(self.check_func):
                    result = await self.check_func()
                else:
                    result = self.check_func()
                
                self._failure_count = 0
                self._last_check_time = time.time()
                
                if isinstance(result, tuple):
                    status, details = result
                else:
                    status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                    details = {}
                
                self._last_status = status
                return status, details
                
            except Exception as e:
                self._failure_count += 1
                self._last_check_time = time.time()
                self._last_status = HealthStatus.UNHEALTHY
                return HealthStatus.UNHEALTHY, {"error": str(e)}
    
    def needs_restart(self) -> bool:
        return self._failure_count >= self.threshold


class HealthCheckManager:
    """Manage multiple health checks and auto-restart."""
    
    def __init__(self, restart_callback: Optional[Callable] = None):
        self.checks: Dict[str, HealthCheck] = {}
        self.restart_callback = restart_callback
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    def register(self, name: str, check_func: Callable, threshold: int = 3):
        """Register a health check."""
        self.checks[name] = HealthCheck(name, check_func, threshold)
    
    async def get_status(self) -> Dict[str, Any]:
        """Get overall health status."""
        results = {}
        overall = HealthStatus.HEALTHY
        
        for name, check in self.checks.items():
            status, details = await check.check()
            results[name] = {"status": status.value, **details}
            
            if status == HealthStatus.UNHEALTHY:
                overall = HealthStatus.DEGRADED
            elif status == HealthStatus.DEGRADED and overall == HealthStatus.HEALTHY:
                overall = HealthStatus.DEGRADED
        
        return {
            "overall": overall.value,
            "checks": results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "healthy_count": sum(1 for r in results.values() if r["status"] == "healthy"),
            "total_count": len(results),
        }
    
    async def _monitor_loop(self, interval: float = 30.0):
        """Background monitoring loop."""
        while self._running:
            try:
                status = await self.get_status()
                
                for name, check in self.checks.items():
                    if check.needs_restart():
                        if self.restart_callback:
                            await self.restart_callback(name)
                        check._failure_count = 0
                
            except Exception:
                pass
            
            await asyncio.sleep(interval)
    
    async def start_monitoring(self, interval: float = 30.0):
        """Start background health monitoring."""
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop(interval))
    
    async def stop_monitoring(self):
        """Stop background health monitoring."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


# ── Graceful Degradation ────────────────────────────────────────────────────────

class GracefulDegradation:
    """
    Graceful degradation system - work with partial system availability.
    """
    
    def __init__(self):
        self._services: Dict[str, bool] = {}
        self._fallbacks: Dict[str, Callable] = {}
        self._lock = asyncio.Lock()
    
    def register_service(self, name: str, fallback: Optional[Callable] = None):
        """Register a service with optional fallback."""
        self._services[name] = True
        if fallback:
            self._fallbacks[name] = fallback
    
    async def mark_healthy(self, name: str):
        """Mark a service as healthy."""
        async with self._lock:
            self._services[name] = True
    
    async def mark_unhealthy(self, name: str):
        """Mark a service as unhealthy."""
        async with self._lock:
            self._services[name] = False
    
    def is_available(self, name: str) -> bool:
        """Check if a service is available."""
        return self._services.get(name, False)
    
    async def call_with_fallback(
        self,
        service: str,
        primary_func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Call a service with fallback on failure."""
        if not self.is_available(service):
            fallback = self._fallbacks.get(service)
            if fallback:
                return await fallback(*args, **kwargs) if asyncio.iscoroutinefunction(fallback) else fallback(*args, **kwargs)
            raise ServiceUnavailableError(f"Service {service} is unavailable")
        
        try:
            if asyncio.iscoroutinefunction(primary_func):
                return await primary_func(*args, **kwargs)
            return primary_func(*args, **kwargs)
        except Exception as e:
            await self.mark_unhealthy(service)
            
            fallback = self._fallbacks.get(service)
            if fallback:
                return await fallback(*args, **kwargs) if asyncio.iscoroutinefunction(fallback) else fallback(*args, **kwargs)
            raise


class ServiceUnavailableError(Exception):
    """Raised when a required service is unavailable."""
    pass


# ── Backup and Restore ─────────────────────────────────────────────────────────

class BackupManager:
    """System state backup and restore."""
    
    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    async def create_backup(self, state_files: List[str], label: Optional[str] = None) -> str:
        """Create a backup of system state files."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_id = f"{timestamp}_{label}" if label else timestamp
        backup_path = self.backup_dir / backup_id
        backup_path.mkdir(parents=True, exist_ok=True)
        
        metadata = {
            "backup_id": backup_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "files": [],
        }
        
        for state_file in state_files:
            src = Path(state_file)
            if src.exists():
                dst = backup_path / src.name
                shutil.copy2(src, dst)
                metadata["files"].append(str(src))
        
        # Save metadata
        with open(backup_path / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return backup_id
    
    async def restore_backup(self, backup_id: str, target_dir: Optional[str] = None) -> bool:
        """Restore a backup."""
        backup_path = self.backup_dir / backup_id
        if not backup_path.exists():
            return False
        
        metadata_file = backup_path / "metadata.json"
        if not metadata_file.exists():
            return False
        
        with open(metadata_file) as f:
            metadata = json.load(f)
        
        target = Path(target_dir) if target_dir else Path.cwd()
        
        for file_path in metadata.get("files", []):
            src = backup_path / Path(file_path).name
            if src.exists():
                dst = target / Path(file_path).name
                shutil.copy2(src, dst)
        
        return True
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups."""
        backups = []
        for backup_path in sorted(self.backup_dir.iterdir()):
            if backup_path.is_dir():
                metadata_file = backup_path / "metadata.json"
                if metadata_file.exists():
                    with open(metadata_file) as f:
                        metadata = json.load(f)
                    backups.append(metadata)
                else:
                    backups.append({
                        "backup_id": backup_path.name,
                        "created_at": datetime.fromtimestamp(
                            backup_path.stat().st_mtime,
                            tz=timezone.utc
                        ).isoformat(),
                    })
        return sorted(backups, key=lambda x: x.get("created_at", ""), reverse=True)
    
    def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup."""
        backup_path = self.backup_dir / backup_id
        if backup_path.exists():
            shutil.rmtree(backup_path)
            return True
        return False


# ── Migration System ───────────────────────────────────────────────────────────

class MigrationManager:
    """Database schema migration system."""
    
    def __init__(self, migrations_dir: str = "migrations", version_file: str = ".db_version"):
        self.migrations_dir = Path(migrations_dir)
        self.migrations_dir.mkdir(parents=True, exist_ok=True)
        self.version_file = Path(version_file)
        self._lock = asyncio.Lock()
    
    def _get_current_version(self) -> int:
        """Get the current database version."""
        if self.version_file.exists():
            try:
                return int(self.version_file.read_text().strip())
            except (ValueError, IOError):
                return 0
        return 0
    
    def _set_current_version(self, version: int):
        """Set the current database version."""
        self.version_file.write_text(str(version))
    
    def register_migration(self, version: int, name: str, up_func: Callable, down_func: Optional[Callable] = None):
        """Register a migration."""
        migration_file = self.migrations_dir / f"{version:04d}_{name}.json"
        
        migration = {
            "version": version,
            "name": name,
            "up": up_func.__name__ if callable(up_func) else str(up_func),
            "down": down_func.__name__ if callable(down_func) and down_func else None,
        }
        
        with open(migration_file, 'w') as f:
            json.dump(migration, f, indent=2)
    
    async def run_migrations(self, db_connection) -> Tuple[int, List[str]]:
        """Run all pending migrations."""
        async with self._lock:
            current_version = self._get_current_version()
            pending_migrations = []
            
            for migration_file in sorted(self.migrations_dir.glob("*.json")):
                try:
                    with open(migration_file) as f:
                        migration = json.load(f)
                    
                    version = migration.get("version", 0)
                    if version > current_version:
                        pending_migrations.append(migration)
                except (json.JSONDecodeError, IOError):
                    continue
            
            applied = []
            for migration in pending_migrations:
                try:
                    # In a real implementation, you'd execute the migration
                    # For now, we just track the version
                    applied.append(f"{migration['version']}: {migration['name']}")
                    self._set_current_version(migration['version'])
                except Exception as e:
                    return current_version, applied, str(e)
            
            return current_version, applied
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get migration status."""
        current = self._get_current_version()
        migrations = []
        
        for migration_file in sorted(self.migrations_dir.glob("*.json")):
            try:
                with open(migration_file) as f:
                    migration = json.load(f)
                migration["applied"] = migration.get("version", 0) <= current
                migrations.append(migration)
            except (json.JSONDecodeError, IOError):
                continue
        
        return {
            "current_version": current,
            "total_migrations": len(migrations),
            "applied_migrations": sum(1 for m in migrations if m.get("applied")),
            "migrations": migrations,
        }


# ── Graceful Shutdown ───────────────────────────────────────────────────────────

class GracefulShutdown:
    """Handle graceful shutdown of the application."""
    
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self._shutdown_handlers: List[Callable] = []
        self._running = False
        self._shutdown_started = False
    
    def register_handler(self, handler: Callable):
        """Register a shutdown handler."""
        self._shutdown_handlers.append(handler)
    
    async def shutdown(self, sig: Optional[str] = None):
        """Execute graceful shutdown."""
        if self._shutdown_started:
            return
        self._shutdown_started = True
        
        print(f"Received shutdown signal: {sig}")
        print("Starting graceful shutdown...")
        
        for handler in self._shutdown_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await asyncio.wait_for(handler(), timeout=self.timeout)
                else:
                    handler()
            except asyncio.TimeoutError:
                print(f"Handler {handler.__name__} timed out")
            except Exception as e:
                print(f"Handler {handler.__name__} failed: {e}")
        
        print("Shutdown complete")
    
    def setup_signal_handlers(self):
        """Setup signal handlers for shutdown."""
        def handle_signal(sig, loop):
            asyncio.create_task(self.shutdown(sig))
        
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda s=sig: handle_signal(s, loop))
        except (NotImplementedError, RuntimeError):
            # Windows doesn't support add_signal_handler
            pass


# ── Global instances ───────────────────────────────────────────────────────────

health_check_manager = HealthCheckManager()
graceful_degradation = GracefulDegradation()
backup_manager = BackupManager()
migration_manager = MigrationManager()
graceful_shutdown = GracefulShutdown()
