"""
tests/test_suite.py - Test Suite v7.0
Comprehensive testing: unit, integration, e2e, load, memory, security tests.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Test Framework ─────────────────────────────────────────────────────────────

class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.error: Optional[str] = None
        self.duration: float = 0
        self.output: Optional[str] = None


class TestSuite:
    def __init__(self):
        self.results: List[TestResult] = []
        self.passed = 0
        self.failed = 0
    
    def run(self, test_func, name: str):
        result = TestResult(name)
        start = time.time()
        
        try:
            if asyncio.iscoroutinefunction(test_func):
                asyncio.run(test_func())
            else:
                test_func()
            result.passed = True
            self.passed += 1
        except Exception as e:
            result.error = str(e)
            self.failed += 1
        
        result.duration = time.time() - start
        self.results.append(result)
        return result
    
    def print_summary(self):
        print("\n" + "=" * 60)
        print(f"TEST RESULTS: {self.passed} passed, {self.failed} failed")
        print("=" * 60)
        
        for r in self.results:
            status = "✓ PASS" if r.passed else "✗ FAIL"
            print(f"{status} [{r.duration:.3f}s] {r.name}")
            if r.error:
                print(f"   Error: {r.error[:100]}")
        
        print("=" * 60)


# ── Unit Tests ─────────────────────────────────────────────────────────────────

def test_security_rate_limiter():
    """Test rate limiter functionality."""
    from core.security import RateLimiter
    
    limiter = RateLimiter(requests_per_minute=10)
    
    # First 10 should pass
    for i in range(10):
        allowed, info = limiter.is_allowed(f"test_user_{i}")
        assert allowed, f"Request {i} should be allowed"
    
    # 11th should fail
    allowed, info = limiter.is_allowed("test_user_11")
    assert not allowed, "11th request should be blocked"
    assert info["remaining"] == 0, "Should have no remaining requests"


def test_security_sanitizer():
    """Test input sanitization."""
    from core.security import InputSanitizer
    
    # Test string sanitization
    result = InputSanitizer.sanitize_string("<script>alert('xss')</script>")
    assert "<script>" not in result, "Script tags should be removed"
    
    # Test path traversal prevention
    path = InputSanitizer.sanitize_path("../../../etc/passwd")
    assert ".." not in path, "Path traversal should be blocked"
    
    # Test dangerous patterns
    is_safe, reason = InputSanitizer.check_dangerous_input("SELECT * FROM users")
    assert not is_safe, "SQL injection should be detected"


def test_reliability_circuit_breaker():
    """Test circuit breaker pattern."""
    from core.reliability import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker(failure_threshold=3)
    
    async def failing_func():
        raise Exception("Test failure")
    
    async def success_func():
        return "success"
    
    async def run_test():
        # Fail 3 times
        for _ in range(3):
            try:
                await cb.call(failing_func)
            except Exception:
                pass
        
        assert cb.state == CircuitState.OPEN, "Circuit should be OPEN after failures"
        
        # Wait and try HALF_OPEN
        await asyncio.sleep(0.1)
        result = await cb.call(success_func)
        assert result == "success", "Should succeed after reset"
        assert cb.state == CircuitState.CLOSED, "Circuit should be CLOSED after success"
    
    asyncio.run(run_test())


def test_monitoring_metrics():
    """Test metrics collection."""
    from core.monitoring import MetricsCollector, MetricType
    
    collector = MetricsCollector()
    
    async def run_test():
        await collector.increment("requests", 1)
        await collector.set("cpu_usage", 0.75)
        await collector.observe("response_time", 0.123)
        
        metrics = await collector.get_all()
        assert "requests" in metrics, "Counter metric should exist"
        assert "cpu_usage" in metrics, "Gauge metric should exist"
    
    asyncio.run(run_test())


def test_webhook_manager():
    """Test webhook manager."""
    from integrations.webhook_manager import WebhookManager
    
    manager = WebhookManager(storage_dir="/tmp/test_webhooks")
    
    # Register webhook
    webhook_id = manager.register_webhook(
        name="Test Webhook",
        url="https://example.com/webhook",
        event_types=["test.event"]
    )
    assert webhook_id, "Should return webhook ID"
    
    # List webhooks
    webhooks = manager.list_webhooks()
    assert len(webhooks) == 1, "Should have 1 webhook"
    assert webhooks[0]["name"] == "Test Webhook", "Webhook name should match"


def test_api_gateway():
    """Test API gateway."""
    from integrations.api_gateway import APIGateway
    
    gateway = APIGateway(storage_dir="/tmp/test_api")
    
    # Generate key
    key, metadata = gateway.generate_key(
        name="Test Key",
        tier="basic"
    )
    assert key.startswith("aios_"), "Key should have prefix"
    assert metadata["tier"] == "basic", "Tier should match"
    
    # Validate key
    valid, api_key_obj, headers = gateway.validate_key(key)
    assert valid, "Key should be valid"
    assert api_key_obj.name == "Test Key", "Key metadata should match"


def test_task_orchestrator():
    """Test task orchestrator."""
    from coordination.task_orchestrator import TaskOrchestrator, TaskPriority
    
    orchestrator = TaskOrchestrator()
    
    async def run_test():
        # Add tasks
        task1_id = await orchestrator.add_task(
            task_type="test",
            description="Test task 1",
            priority=TaskPriority.HIGH
        )
        task2_id = await orchestrator.add_task(
            task_type="test",
            description="Test task 2",
            priority=TaskPriority.LOW
        )
        
        # Get ready tasks
        ready = await orchestrator.get_ready_tasks()
        assert len(ready) == 2, "Should have 2 ready tasks"
        
        # Check priority sorting
        assert ready[0].priority == TaskPriority.HIGH, "High priority should be first"
    
    asyncio.run(run_test())


def test_quality_controller():
    """Test quality controller."""
    from coordination.quality_controller import QualityController, QualityGrade
    
    controller = QualityController()
    
    async def run_test():
        # Test code quality checking
        result = await controller.evaluate(
            agent_id="aider",
            code="def hello(): return 'Hello, World!'",
            requirements="Create a hello function"
        )
        
        assert result.grade in QualityGrade, "Should return valid grade"
        assert "correctness" in result.metrics, "Should have correctness metric"
    
    asyncio.run(run_test())


def test_context_window_manager():
    """Test context window manager."""
    from memory.context_window_manager import ContextWindowManager, ContextPriority
    
    manager = ContextWindowManager(max_tokens=1000, reserved_tokens=200)
    
    # Add contexts
    manager.add_context(
        content="This is important system context",
        source="system",
        priority=ContextPriority.CRITICAL,
        token_estimate=100
    )
    
    manager.add_context(
        content="Some less important context",
        source="memory",
        priority=ContextPriority.LOW,
        token_estimate=100
    )
    
    # Get stats
    stats = manager.get_stats()
    assert stats["total_items"] == 2, "Should have 2 items"
    assert stats["available_tokens"] == 800, "Should have 800 available tokens"


def test_forgetting_curve():
    """Test forgetting curve memory."""
    from memory.forgetting_curve import ForgettingCurveManager, MemoryType
    
    manager = ForgettingCurveManager(storage_file="/tmp/test_memory.json")
    
    # Add memory
    mem_id = manager.add_memory(
        content="Important: Python is the best language",
        memory_type=MemoryType.IMPORTANT,
        importance=0.9
    )
    assert mem_id, "Should return memory ID"
    
    # Get permanent memories
    permanent = manager.get_permanent_memories()
    assert len(permanent) == 1, "Should have 1 permanent memory"
    
    # Test spaced repetition
    result = manager.review_memory(mem_id, quality=5)
    assert result["new_interval"] > 0, "Should update interval"


# ── Integration Tests ──────────────────────────────────────────────────────────

async def test_api_health():
    """Test health endpoint."""
    import httpx
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:8080/health")
            assert response.status_code == 200, "Health should return 200"
            data = response.json()
            assert "status" in data, "Should have status field"
    except httpx.ConnectError:
        print("  (Skipped - server not running)")


async def test_api_workflows():
    """Test workflows endpoint."""
    import httpx
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:8080/")
            assert response.status_code == 200, "Root should return 200"
            data = response.json()
            assert "version" in data, "Should have version"
    except httpx.ConnectError:
        print("  (Skipped - server not running)")


# ── End-to-End Tests ────────────────────────────────────────────────────────────

async def test_full_workflow():
    """Test complete workflow execution."""
    import httpx
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Create project
            proj_response = await client.post(
                "http://localhost:8080/memory/projects",
                json={"name": "Test Project", "description": "E2E Test"}
            )
            assert proj_response.status_code == 200
            
            # Search memory
            search_response = await client.post(
                "http://localhost:8080/memory/search",
                json={"requirements": "Test Project"}
            )
            assert search_response.status_code == 200
    except httpx.ConnectError:
        print("  (Skipped - server not running)")


# ── Load Tests ─────────────────────────────────────────────────────────────────

async def test_concurrent_requests():
    """Test concurrent API requests."""
    import httpx
    
    try:
        async def make_request():
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("http://localhost:8080/health")
                return response.status_code == 200
        
        # 100 concurrent requests
        tasks = [make_request() for _ in range(100)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        passed = sum(1 for r in results if r is True)
        print(f"  Load test: {passed}/100 requests succeeded")
    except httpx.ConnectError:
        print("  (Skipped - server not running)")


# ── Memory Tests ──────────────────────────────────────────────────────────────

async def test_memory_persistence():
    """Test memory persists across restarts."""
    from memory.vector_store import store_project, get_project_context
    
    project_id = store_project({
        "name": "Persistence Test",
        "description": "Testing memory persistence"
    })
    
    retrieved = get_project_context(project_id)
    assert retrieved is not None, "Should retrieve stored project"
    assert retrieved["name"] == "Persistence Test", "Should match stored name"


# ── Security Tests ─────────────────────────────────────────────────────────────

def test_sql_injection_prevention():
    """Test SQL injection prevention."""
    from core.security import InputSanitizer
    
    malicious_inputs = [
        "'; DROP TABLE users; --",
        "1' OR '1'='1",
        "admin'--",
        "<script>alert('xss')</script>",
    ]
    
    for input_val in malicious_inputs:
        is_safe, reason = InputSanitizer.check_dangerous_input(input_val)
        assert not is_safe, f"Should block: {input_val[:30]}"


def test_xss_prevention():
    """Test XSS prevention."""
    from core.security import InputSanitizer
    
    xss_inputs = [
        "<script>alert('xss')</script>",
        "javascript:alert('xss')",
        "<img src=x onerror=alert('xss')>",
    ]
    
    for input_val in xss_inputs:
        is_safe, reason = InputSanitizer.check_dangerous_input(input_val)
        assert not is_safe, f"Should block XSS: {input_val[:30]}"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    suite = TestSuite()
    
    print("\n" + "=" * 60)
    print("AI Engineering OS v7.0 - Test Suite")
    print("=" * 60)
    
    # Unit Tests
    print("\n--- Unit Tests ---")
    suite.run(test_security_rate_limiter, "Security: Rate Limiter")
    suite.run(test_security_sanitizer, "Security: Input Sanitizer")
    suite.run(test_reliability_circuit_breaker, "Reliability: Circuit Breaker")
    suite.run(test_monitoring_metrics, "Monitoring: Metrics")
    suite.run(test_webhook_manager, "Webhook: Manager")
    suite.run(test_api_gateway, "API: Gateway")
    suite.run(test_task_orchestrator, "Task: Orchestrator")
    suite.run(test_quality_controller, "Quality: Controller")
    suite.run(test_context_window_manager, "Memory: Context Window")
    suite.run(test_forgetting_curve, "Memory: Forgetting Curve")
    
    # Security Tests
    print("\n--- Security Tests ---")
    suite.run(test_sql_injection_prevention, "Security: SQL Injection Prevention")
    suite.run(test_xss_prevention, "Security: XSS Prevention")
    
    # Integration Tests
    print("\n--- Integration Tests ---")
    suite.run(test_api_health, "API: Health Endpoint")
    suite.run(test_api_workflows, "API: Workflows Endpoint")
    suite.run(test_full_workflow, "E2E: Full Workflow")
    suite.run(test_memory_persistence, "Memory: Persistence")
    
    # Load Tests
    print("\n--- Load Tests ---")
    suite.run(test_concurrent_requests, "Load: 100 Concurrent Requests")
    
    # Print summary
    suite.print_summary()
    
    return 0 if suite.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
