"""
core/security.py - Production Security Module v7.0
Comprehensive security hardening for the AI Engineering OS.
"""

import hashlib
import hmac
import json
import re
import secrets
import time
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml

# ── Rate Limiting ──────────────────────────────────────────────────────────────

class RateLimiter:
    """Token bucket rate limiter with configurable limits per IP/key."""
    
    def __init__(self, requests_per_minute: int = 100, burst_size: Optional[int] = None):
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size or requests_per_minute
        self._buckets: Dict[str, Tuple[float, int]] = {}
        self._lock_key = None  # asyncio.Lock managed externally
    
    def _get_key(self, identifier: str) -> str:
        return hashlib.sha256(identifier.encode()).hexdigest()[:16]
    
    def is_allowed(self, identifier: str) -> Tuple[bool, Dict[str, Any]]:
        key = self._get_key(identifier)
        now = time.time()
        
        if key not in self._buckets:
            self._buckets[key] = (now, self.burst_size - 1)
            return True, {"remaining": self.burst_size - 1, "reset": 60}
        
        timestamp, tokens = self._buckets[key]
        elapsed = now - timestamp
        
        # Refill tokens based on elapsed time
        refill = int(elapsed * (self.requests_per_minute / 60))
        new_tokens = min(self.burst_size, tokens + refill)
        
        if new_tokens <= 0:
            retry_after = int(60 / self.requests_per_minute)
            return False, {
                "remaining": 0,
                "reset": retry_after,
                "retry_after": retry_after
            }
        
        self._buckets[key] = (now, new_tokens - 1)
        return True, {
            "remaining": new_tokens - 1,
            "reset": 60
        }
    
    def cleanup_old_entries(self, max_age_seconds: int = 3600):
        """Remove stale rate limit entries."""
        now = time.time()
        expired = [k for k, (ts, _) in self._buckets.items() if now - ts > max_age_seconds]
        for k in expired:
            del self._buckets[k]


# ── Input Sanitization ─────────────────────────────────────────────────────────

class InputSanitizer:
    """Sanitize and validate all user inputs."""
    
    # Dangerous patterns that should never appear in user input
    DANGEROUS_PATTERNS = [
        (r'<script[^>]*>.*?</script>', 'script injection'),
        (r'javascript:', 'javascript protocol'),
        (r'on\w+\s*=', 'event handler'),
        (r'<iframe[^>]*>.*?</iframe>', 'iframe injection'),
        (r'<object[^>]*>.*?</object>', 'object injection'),
        (r'<embed[^>]*>', 'embed injection'),
        (r'\.\./', 'path traversal'),
        (r'[\x00-\x08\x0b\x0c\x0e-\x1f]', 'control characters'),
    ]
    
    SQL_INJECTION_PATTERNS = [
        (r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|TRUNCATE|EXEC|EXECUTE)\b)", 'SQL keyword'),
        (r"(--|#|\/\*)", 'SQL comment'),
        (r"('|(\\'))", 'SQL quote injection'),
        (r"(;|\|\||&&)", 'SQL separator'),
    ]
    
    @classmethod
    def sanitize_string(cls, value: str, max_length: int = 10000) -> str:
        """Sanitize a string input."""
        if not isinstance(value, str):
            return str(value)[:max_length]
        
        # Remove null bytes and control characters
        value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)
        
        # Trim to max length
        value = value[:max_length]
        
        return value.strip()
    
    @classmethod
    def sanitize_path(cls, path: str) -> str:
        """Sanitize a file path to prevent traversal attacks."""
        # Remove dangerous patterns
        path = re.sub(r'\.\./', '', path)
        path = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', path)
        
        # Resolve and validate
        try:
            resolved = Path(path).resolve()
            # Ensure path doesn't escape workspace
            if str(resolved).startswith('/workspace') or str(resolved).startswith('.'):
                return str(resolved)
        except (ValueError, OSError):
            pass
        
        return '.'
    
    @classmethod
    def check_dangerous_input(cls, value: str) -> Tuple[bool, Optional[str]]:
        """Check for dangerous input patterns."""
        if not isinstance(value, str):
            return True, None
        
        for pattern, description in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE | re.DOTALL):
                return False, f"Dangerous pattern detected: {description}"
        
        for pattern, description in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return False, f"SQL injection pattern detected: {description}"
        
        return True, None
    
    @classmethod
    def validate_json(cls, data: Any, schema: Optional[Dict] = None) -> Tuple[bool, Optional[str]]:
        """Validate JSON data against a schema."""
        if schema is None:
            return True, None
        
        def validate_value(value: Any, schema_def: Dict, path: str = "root") -> Tuple[bool, Optional[str]]:
            if "type" in schema_def:
                expected_type = schema_def["type"]
                if expected_type == "string" and not isinstance(value, str):
                    return False, f"{path}: expected string"
                elif expected_type == "number" and not isinstance(value, (int, float)):
                    return False, f"{path}: expected number"
                elif expected_type == "boolean" and not isinstance(value, bool):
                    return False, f"{path}: expected boolean"
                elif expected_type == "array" and not isinstance(value, list):
                    return False, f"{path}: expected array"
                elif expected_type == "object" and not isinstance(value, dict):
                    return False, f"{path}: expected object"
            
            if "enum" in schema_def and value not in schema_def["enum"]:
                return False, f"{path}: value not in allowed values"
            
            if "minLength" in schema_def and isinstance(value, str) and len(value) < schema_def["minLength"]:
                return False, f"{path}: string too short"
            
            if "maxLength" in schema_def and isinstance(value, str) and len(value) > schema_def["maxLength"]:
                return False, f"{path}: string too long"
            
            if "properties" in schema_def and isinstance(value, dict):
                for prop, prop_schema in schema_def["properties"].items():
                    if "required" in schema_def and prop in schema_def["required"]:
                        if prop not in value:
                            return False, f"{path}.{prop}: required field missing"
                    if prop in value:
                        valid, err = validate_value(value[prop], prop_schema, f"{path}.{prop}")
                        if not valid:
                            return valid, err
            
            return True, None
        
        return validate_value(data, schema)


# ── API Key Management ─────────────────────────────────────────────────────────

class APIKeyManager:
    """Generate, validate, and manage API keys."""
    
    def __init__(self, keys_file: str = "config/api_keys.json"):
        self.keys_file = Path(keys_file)
        self._keys: Dict[str, Dict] = {}
        self._load_keys()
    
    def _load_keys(self):
        """Load API keys from file."""
        if self.keys_file.exists():
            try:
                with open(self.keys_file) as f:
                    self._keys = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._keys = {}
    
    def _save_keys(self):
        """Persist API keys to file."""
        self.keys_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.keys_file, 'w') as f:
            json.dump(self._keys, f, indent=2)
    
    def generate_key(self, name: str, rate_limit: int = 100, 
                    permissions: Optional[List[str]] = None) -> str:
        """Generate a new API key."""
        key = f"aios_{secrets.token_urlsafe(32)}"
        self._keys[key] = {
            "name": name,
            "rate_limit": rate_limit,
            "permissions": permissions or ["read"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_used": None,
            "use_count": 0,
            "active": True
        }
        self._save_keys()
        return key
    
    def validate_key(self, key: str) -> Tuple[bool, Optional[Dict]]:
        """Validate an API key and return its metadata."""
        if key not in self._keys:
            return False, None
        
        key_data = self._keys[key]
        if not key_data.get("active", False):
            return False, None
        
        # Update last used
        key_data["last_used"] = datetime.now(timezone.utc).isoformat()
        key_data["use_count"] = key_data.get("use_count", 0) + 1
        self._save_keys()
        
        return True, key_data
    
    def revoke_key(self, key: str) -> bool:
        """Revoke an API key."""
        if key in self._keys:
            self._keys[key]["active"] = False
            self._save_keys()
            return True
        return False
    
    def get_key_metadata(self, key: str) -> Optional[Dict]:
        """Get metadata for an API key (without exposing the key)."""
        if key not in self._keys:
            return None
        
        data = dict(self._keys[key])
        data.pop("active", None)
        return data


# ── CORS Configuration ──────────────────────────────────────────────────────────

class CORSConfig:
    """CORS configuration helper."""
    
    DEFAULT_ALLOWED_ORIGINS = {"*"}
    DEFAULT_ALLOWED_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"}
    DEFAULT_ALLOWED_HEADERS = {"Content-Type", "Authorization", "X-API-Key"}
    DEFAULT_EXPOSED_HEADERS = {"X-Request-ID", "X-RateLimit-Remaining"}
    DEFAULT_MAX_AGE = 3600
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        return {
            "allow_origins": list(cls.DEFAULT_ALLOWED_ORIGINS),
            "allow_methods": list(cls.DEFAULT_ALLOWED_METHODS),
            "allow_headers": list(cls.DEFAULT_ALLOWED_HEADERS),
            "expose_headers": list(cls.DEFAULT_EXPOSED_HEADERS),
            "allow_credentials": True,
            "max_age": cls.DEFAULT_MAX_AGE,
        }


# ── Security Headers ───────────────────────────────────────────────────────────

class SecurityHeaders:
    """Generate security headers for HTTP responses."""
    
    @staticmethod
    def get_headers() -> Dict[str, str]:
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:;",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "accelerometer=(), camera=(), microphone=(), geolocation=()",
            "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0",
            "Pragma": "no-cache",
        }


# ── Webhook Signature Verification ──────────────────────────────────────────────

class WebhookVerifier:
    """Verify webhook signatures using HMAC."""
    
    @staticmethod
    def verify_github_signature(payload: bytes, signature: str, secret: str) -> bool:
        """Verify GitHub webhook signature."""
        expected = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(f"sha256={expected}", signature)
    
    @staticmethod
    def verify_slack_signature(payload: bytes, timestamp: str, signature: str, secret: str) -> bool:
        """Verify Slack webhook signature."""
        sig_basestring = f"v0:{timestamp}:{payload.decode()}"
        expected = "v0=" + hmac.new(
            secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    
    @staticmethod
    def generate_signature(payload: str, secret: str, algorithm: str = "sha256") -> str:
        """Generate a webhook signature."""
        if algorithm == "sha256":
            return "sha256=" + hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
        raise ValueError(f"Unsupported algorithm: {algorithm}")


# ── Request Decorators ─────────────────────────────────────────────────────────

def rate_limit(requests_per_minute: int = 100):
    """Decorator to rate limit an endpoint."""
    limiter = RateLimiter(requests_per_minute)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request, *args, **kwargs):
            identifier = request.client.host if hasattr(request, 'client') else 'unknown'
            allowed, info = limiter.is_allowed(identifier)
            
            if not allowed:
                return {
                    "error": "Rate limit exceeded",
                    "retry_after": info.get("retry_after", 60)
                }
            
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_api_key(permissions: Optional[List[str]] = None):
    """Decorator to require a valid API key."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request, *args, **kwargs):
            api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization", "").replace("Bearer ", "")
            
            if not api_key:
                return {"error": "API key required"}
            
            manager = APIKeyManager()
            valid, key_data = manager.validate_key(api_key)
            
            if not valid:
                return {"error": "Invalid API key"}
            
            if permissions:
                key_perms = key_data.get("permissions", [])
                if not any(p in key_perms for p in permissions):
                    return {"error": "Insufficient permissions"}
            
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


# ── Audit Logging ──────────────────────────────────────────────────────────────

class AuditLogger:
    """Log security-relevant events."""
    
    def __init__(self, log_file: str = "logs/audit.log"):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, event_type: str, details: Dict[str, Any], 
            user: Optional[str] = None, ip: Optional[str] = None):
        """Log a security event."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "user": user,
            "ip": ip,
            "details": details
        }
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(entry) + "\n")
        except IOError:
            pass  # Don't crash on logging failures


# ── Global instances ───────────────────────────────────────────────────────────

# Global rate limiter for general API endpoints
general_rate_limiter = RateLimiter(requests_per_minute=100)

# Global rate limiter for strict endpoints (auth, admin)
strict_rate_limiter = RateLimiter(requests_per_minute=10)

# API key manager
api_key_manager = APIKeyManager()

# Audit logger
audit_logger = AuditLogger()

# Input sanitizer
input_sanitizer = InputSanitizer()
