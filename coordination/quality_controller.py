"""
coordination/quality_controller.py - Quality Controller v7.0
Grade agent outputs, auto-rework failures, escalate to human on repeated failures.
"""

import asyncio
import difflib
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

# ── Quality Enums ─────────────────────────────────────────────────────────────

class QualityGrade(Enum):
    EXCELLENT = "excellent"   # Passes all checks
    GOOD = "good"              # Minor issues
    ACCEPTABLE = "acceptable"  # Needs minor fixes
    POOR = "poor"              # Needs rework
    FAILED = "failed"          # Major issues


class QualityMetric(Enum):
    CORRECTNESS = "correctness"
    COMPLETENESS = "completeness"
    STYLE = "style"
    SECURITY = "security"
    PERFORMANCE = "performance"
    TESTING = "testing"


# ── Quality Thresholds ────────────────────────────────────────────────────────

@dataclass
class QualityThreshold:
    """Quality threshold for an agent type."""
    agent_type: str
    min_score: float = 0.7
    metrics: Dict[QualityMetric, float] = field(default_factory=lambda: {
        QualityMetric.CORRECTNESS: 0.8,
        QualityMetric.COMPLETENESS: 0.7,
        QualityMetric.STYLE: 0.6,
        QualityMetric.SECURITY: 0.9,
        QualityMetric.PERFORMANCE: 0.7,
        QualityMetric.TESTING: 0.6,
    })


# ── Quality Result ────────────────────────────────────────────────────────────

@dataclass
class QualityResult:
    """Result of a quality check."""
    grade: QualityGrade
    overall_score: float
    metrics: Dict[QualityMetric, float]
    issues: List[str]
    suggestions: List[str]
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)


# ── Code Quality Checker ─────────────────────────────────────────────────────

class CodeQualityChecker:
    """Check code quality metrics."""
    
    def __init__(self):
        self._security_patterns = self._load_security_patterns()
    
    def _load_security_patterns(self) -> List[Tuple[str, str]]:
        """Load dangerous code patterns."""
        return [
            (r"eval\s*\(", "Use of eval() is dangerous"),
            (r"exec\s*\(", "Use of exec() is dangerous"),
            (r"__import__\s*\(", "Dynamic import can be dangerous"),
            (r"pickle\.load", "Unsafe deserialization with pickle"),
            (r"yaml\.load\s*\(", "Use SafeLoader for YAML"),
            (r"subprocess\..*shell\s*=\s*True", "Shell injection risk"),
            (r"password\s*=\s*['\"][^'\"]{0,}", "Hardcoded password detected"),
            (r"api[_-]?key\s*=\s*['\"][^'\"]{0,}", "Hardcoded API key detected"),
            (r"token\s*=\s*['\"][^'\"]{0,}", "Hardcoded token detected"),
            (r"secrets\.(?:password|token|key)", "Hardcoded secret detected"),
            (r"SQl\s*(?:INJECTION|Query)", "SQL injection risk pattern"),
            (r"<script[^>]*>", "Potential XSS vulnerability"),
        ]
    
    async def check_correctness(
        self,
        code: str,
        requirements: str
    ) -> Tuple[float, List[str]]:
        """Check code correctness against requirements."""
        issues = []
        score = 1.0
        
        # Check if all requirements are addressed
        req_keywords = self._extract_keywords(requirements)
        code_keywords = self._extract_keywords(code)
        
        missing = req_keywords - code_keywords
        if missing:
            issues.append(f"Missing keywords from requirements: {missing}")
            score -= 0.1 * len(missing)
        
        # Check for syntax errors
        try:
            compile(code, '<string>', 'exec')
        except SyntaxError as e:
            issues.append(f"Syntax error: {e}")
            score -= 0.3
        
        return max(0, score), issues
    
    async def check_completeness(
        self,
        code: str,
        requirements: str
    ) -> Tuple[float, List[str]]:
        """Check if implementation is complete."""
        issues = []
        score = 1.0
        
        # Count function/class definitions
        func_count = len(re.findall(r'def\s+\w+', code))
        class_count = len(re.findall(r'class\s+\w+', code))
        
        # Check for TODO/FIXME
        todo_count = len(re.findall(r'(TODO|FIXME|HACK|XXX)', code, re.IGNORECASE))
        if todo_count > 0:
            issues.append(f"Found {todo_count} incomplete markers (TODO/FIXME)")
            score -= 0.05 * todo_count
        
        # Check for placeholder comments
        placeholder_count = len(re.findall(r'#.*(?:placeholder|implement|later)', code, re.IGNORECASE))
        if placeholder_count > 0:
            issues.append(f"Found {placeholder_count} placeholder implementations")
            score -= 0.1 * placeholder_count
        
        return max(0, score), issues
    
    async def check_style(
        self,
        code: str
    ) -> Tuple[float, List[str]]:
        """Check code style."""
        issues = []
        score = 1.0
        
        lines = code.split('\n')
        
        # Check line length
        long_lines = [(i+1, len(line)) for i, line in enumerate(lines) if len(line) > 120]
        if long_lines:
            issues.append(f"Found {len(long_lines)} lines over 120 characters")
            score -= 0.02 * len(long_lines)
        
        # Check for trailing whitespace
        trailing_ws = sum(1 for line in lines if line.rstrip() != line)
        if trailing_ws:
            issues.append(f"Found {trailing_ws} lines with trailing whitespace")
            score -= 0.01 * trailing_ws
        
        # Check naming conventions
        snake_case = len(re.findall(r'\b[a-z][a-z0-9_]*\b', code))
        camel_case = len(re.findall(r'\b[a-z][A-Z]\w*\b', code))
        
        if camel_case > snake_case * 0.3:
            issues.append("Mixing naming conventions (snake_case and camelCase)")
            score -= 0.05
        
        return max(0, score), issues
    
    async def check_security(
        self,
        code: str
    ) -> Tuple[float, List[str]]:
        """Check for security issues."""
        issues = []
        score = 1.0
        
        for pattern, description in self._security_patterns:
            matches = re.findall(pattern, code, re.IGNORECASE)
            if matches:
                issues.append(description)
                score -= 0.15
        
        # Check for SQL injection patterns
        sql_patterns = [
            r'["\']\s*(?:SELECT|INSERT|UPDATE|DELETE).*?["\'].*?%',
            r'["\'].*?%\s*(?:SELECT|INSERT|UPDATE|DELETE)',
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                issues.append("Potential SQL injection vulnerability")
                score -= 0.2
                break
        
        return max(0, score), issues
    
    async def check_performance(
        self,
        code: str
    ) -> Tuple[float, List[str]]:
        """Check for performance issues."""
        issues = []
        score = 1.0
        
        # Check for nested loops
        nested_loops = self._count_nested_loops(code)
        if nested_loops > 2:
            issues.append(f"Deeply nested loops ({nested_loops} levels) - potential O(n^2+)")
            score -= 0.05 * (nested_loops - 2)
        
        # Check for list comprehensions that could be generators
        list_comp_count = len(re.findall(r'\[.*for.*in.*for.*in.*\]', code))
        if list_comp_count > 5:
            issues.append(f"Found {list_comp_count} nested list comprehensions - consider generators")
            score -= 0.02 * list_comp_count
        
        # Check for repeated string concatenation
        string_concat = len(re.findall(r'\+\s*["\']', code))
        if string_concat > 10:
            issues.append("Multiple string concatenations - consider f-strings or join()")
            score -= 0.01 * (string_concat - 10)
        
        return max(0, score), issues
    
    async def check_testing(
        self,
        code: str,
        tests: str
    ) -> Tuple[float, List[str]]:
        """Check testing coverage."""
        issues = []
        score = 1.0
        
        if not tests:
            issues.append("No tests provided")
            return 0.3, issues
        
        # Count test functions
        test_funcs = len(re.findall(r'def\s+test_\w+', tests))
        code_funcs = len(re.findall(r'def\s+\w+', code))
        
        if code_funcs > 0:
            coverage_ratio = test_funcs / code_funcs
            if coverage_ratio < 0.5:
                issues.append(f"Low test coverage: {coverage_ratio:.0%}")
                score = coverage_ratio
        
        # Check for assertions
        assertion_count = len(re.findall(r'assert\s+', tests))
        if assertion_count < test_funcs:
            issues.append(f"Tests missing assertions ({test_funcs} tests, {assertion_count} assertions)")
            score -= 0.1
        
        return max(0, min(1, score)), issues
    
    def _extract_keywords(self, text: str) -> set:
        """Extract meaningful keywords from text."""
        # Remove common words
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                    'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
                    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                    'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those', 'it'}
        
        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', text.lower())
        return set(w for w in words if w not in stopwords and len(w) > 2)
    
    def _count_nested_loops(self, code: str) -> int:
        """Count maximum loop nesting depth."""
        max_depth = 0
        current_depth = 0
        
        for line in code.split('\n'):
            # Remove comments
            line = re.sub(r'#.*', '', line)
            
            # Count loop keywords
            for match in re.finditer(r'\b(for|while)\b', line):
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            
            # Dedent detection (simplified)
            if current_depth > 0 and line.strip() and not any(k in line for k in ['for', 'while', 'if', 'else', 'elif', 'try', 'except']):
                # Check indentation (simplified)
                pass
        
        return max_depth


# ── Quality Controller ────────────────────────────────────────────────────────

class QualityController:
    """
    Production quality controller that grades agent outputs and manages rework.
    """
    
    def __init__(self):
        self._thresholds: Dict[str, QualityThreshold] = {}
        self._grade_history: Dict[str, List[QualityGrade]] = {}
        self._escalation_callback: Optional[Callable] = None
        self._lock = asyncio.Lock()
        
        self.quality_checker = CodeQualityChecker()
        
        # Set default thresholds
        self._set_default_thresholds()
    
    def _set_default_thresholds(self):
        """Set default quality thresholds."""
        self._thresholds["openhands"] = QualityThreshold(
            agent_type="openhands",
            min_score=0.8,
            metrics={
                QualityMetric.CORRECTNESS: 0.85,
                QualityMetric.COMPLETENESS: 0.8,
                QualityMetric.STYLE: 0.7,
                QualityMetric.SECURITY: 0.95,
                QualityMetric.PERFORMANCE: 0.75,
                QualityMetric.TESTING: 0.7,
            }
        )
        
        self._thresholds["aider"] = QualityThreshold(
            agent_type="aider",
            min_score=0.7,
            metrics={
                QualityMetric.CORRECTNESS: 0.8,
                QualityMetric.COMPLETENESS: 0.7,
                QualityMetric.STYLE: 0.75,
                QualityMetric.SECURITY: 0.85,
                QualityMetric.PERFORMANCE: 0.7,
                QualityMetric.TESTING: 0.6,
            }
        )
        
        self._thresholds["bolt"] = QualityThreshold(
            agent_type="bolt",
            min_score=0.65,
            metrics={
                QualityMetric.CORRECTNESS: 0.75,
                QualityMetric.COMPLETENESS: 0.7,
                QualityMetric.STYLE: 0.7,
                QualityMetric.SECURITY: 0.8,
                QualityMetric.PERFORMANCE: 0.7,
                QualityMetric.TESTING: 0.5,
            }
        )
        
        self._thresholds["replit"] = QualityThreshold(
            agent_type="replit",
            min_score=0.7,
            metrics={
                QualityMetric.CORRECTNESS: 0.8,
                QualityMetric.COMPLETENESS: 0.7,
                QualityMetric.STYLE: 0.65,
                QualityMetric.SECURITY: 0.8,
                QualityMetric.PERFORMANCE: 0.8,
                QualityMetric.TESTING: 0.6,
            }
        )
    
    def set_threshold(self, agent_type: str, threshold: QualityThreshold):
        """Set quality threshold for an agent type."""
        self._thresholds[agent_type] = threshold
    
    def set_escalation_callback(self, callback: Callable):
        """Set callback for human escalation."""
        self._escalation_callback = callback
    
    async def evaluate(
        self,
        agent_id: str,
        code: str,
        requirements: str,
        tests: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> QualityResult:
        """Evaluate the quality of agent output."""
        async with self._lock:
            # Get threshold for agent
            threshold = self._thresholds.get(agent_id, QualityThreshold(agent_type=agent_id))
            
            # Run all checks
            correctness, c_issues = await self.quality_checker.check_correctness(code, requirements)
            completeness, comp_issues = await self.quality_checker.check_completeness(code, requirements)
            style, style_issues = await self.quality_checker.check_style(code)
            security, sec_issues = await self.quality_checker.check_security(code)
            performance, perf_issues = await self.quality_checker.check_performance(code)
            testing, test_issues = await self.quality_checker.check_testing(code, tests)
            
            # Calculate weighted score
            metrics = {
                QualityMetric.CORRECTNESS: correctness,
                QualityMetric.COMPLETENESS: completeness,
                QualityMetric.STYLE: style,
                QualityMetric.SECURITY: security,
                QualityMetric.PERFORMANCE: performance,
                QualityMetric.TESTING: testing,
            }
            
            # Weighted average
            weights = {
                QualityMetric.CORRECTNESS: 0.3,
                QualityMetric.COMPLETENESS: 0.2,
                QualityMetric.STYLE: 0.1,
                QualityMetric.SECURITY: 0.2,
                QualityMetric.PERFORMANCE: 0.1,
                QualityMetric.TESTING: 0.1,
            }
            
            overall_score = sum(
                metrics[m] * weights[m]
                for m in QualityMetric
            )
            
            # Collect all issues
            all_issues = c_issues + comp_issues + style_issues + sec_issues + perf_issues + test_issues
            
            # Generate suggestions
            suggestions = self._generate_suggestions(metrics, threshold.metrics)
            
            # Determine grade
            if overall_score >= 0.9:
                grade = QualityGrade.EXCELLENT
            elif overall_score >= 0.8:
                grade = QualityGrade.GOOD
            elif overall_score >= 0.7:
                grade = QualityGrade.ACCEPTABLE
            elif overall_score >= 0.5:
                grade = QualityGrade.POOR
            else:
                grade = QualityGrade.FAILED
            
            # Determine if passed
            passed = overall_score >= threshold.min_score
            
            # Check metric thresholds
            for metric, score in metrics.items():
                if score < threshold.metrics.get(metric, 0.5):
                    passed = False
            
            result = QualityResult(
                grade=grade,
                overall_score=round(overall_score, 3),
                metrics={m.value: round(v, 3) for m, v in metrics.items()},
                issues=all_issues,
                suggestions=suggestions,
                passed=passed,
                details={
                    "agent_id": agent_id,
                    "threshold": threshold.min_score,
                    "timestamp": time.time(),
                    **(metadata or {})
                }
            )
            
            # Update history
            self._update_history(agent_id, grade)
            
            # Check for escalation
            if not passed:
                await self._handle_failed_output(agent_id, result)
            
            return result
    
    def _generate_suggestions(
        self,
        metrics: Dict[QualityMetric, float],
        thresholds: Dict[QualityMetric, float]
    ) -> List[str]:
        """Generate improvement suggestions."""
        suggestions = []
        
        for metric, score in metrics.items():
            threshold = thresholds.get(metric, 0.5)
            
            if score < threshold:
                if metric == QualityMetric.CORRECTNESS:
                    suggestions.append("Review the implementation against requirements more carefully")
                elif metric == QualityMetric.COMPLETENESS:
                    suggestions.append("Ensure all requirements are fully implemented")
                elif metric == QualityMetric.STYLE:
                    suggestions.append("Improve code style and formatting")
                elif metric == QualityMetric.SECURITY:
                    suggestions.append("Address security concerns in the code")
                elif metric == QualityMetric.PERFORMANCE:
                    suggestions.append("Optimize performance-critical sections")
                elif metric == QualityMetric.TESTING:
                    suggestions.append("Add more comprehensive tests")
        
        return suggestions
    
    def _update_history(self, agent_id: str, grade: QualityGrade):
        """Update grade history for an agent."""
        if agent_id not in self._grade_history:
            self._grade_history[agent_id] = []
        
        self._grade_history[agent_id].append(grade)
        
        # Keep only last 100 grades
        if len(self._grade_history[agent_id]) > 100:
            self._grade_history[agent_id] = self._grade_history[agent_id][-100:]
    
    async def _handle_failed_output(self, agent_id: str, result: QualityResult):
        """Handle a failed quality check."""
        # Count recent failures
        history = self._grade_history.get(agent_id, [])
        recent_failures = sum(
            1 for g in history[-3:]
            if g in (QualityGrade.POOR, QualityGrade.FAILED)
        )
        
        if recent_failures >= 3 and self._escalation_callback:
            # Escalate to human
            await self._escalation_callback(agent_id, result)
    
    async def should_retry(self, agent_id: str) -> Tuple[bool, int]:
        """Check if agent should retry (not exceeded max failures)."""
        history = self._grade_history.get(agent_id, [])
        recent_failures = sum(
            1 for g in history[-3:]
            if g in (QualityGrade.POOR, QualityGrade.FAILED)
        )
        
        # Allow retry if less than 3 recent failures
        return recent_failures < 3, 3 - recent_failures
    
    async def get_agent_performance(self, agent_id: str) -> Dict[str, Any]:
        """Get performance statistics for an agent."""
        history = self._grade_history.get(agent_id, [])
        
        if not history:
            return {"total": 0, "grade_distribution": {}}
        
        grades = [g.value for g in history]
        
        return {
            "total": len(grades),
            "grade_distribution": {
                "excellent": grades.count("excellent"),
                "good": grades.count("good"),
                "acceptable": grades.count("acceptable"),
                "poor": grades.count("poor"),
                "failed": grades.count("failed"),
            },
            "pass_rate": (len(grades) - grades.count("failed") - grades.count("poor")) / len(grades),
            "recent_trend": grades[-5:] if len(grades) >= 5 else grades,
        }


# ── Global instance ───────────────────────────────────────────────────────────

quality_controller = QualityController()
