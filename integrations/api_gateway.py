"""
integrations/api_gateway.py - API Gateway v7.0
Rate limiting, API key generation/management, request logging, usage quotas, versioning.
"""

import asyncio
import json
import secrets
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# ── Rate Limiting ─────────────────────────────────────────────────────────────

class RateLimitTier(Enum):
    FREE = ("free", 100, 1000)      # (name, req/min, req/day)
    BASIC = ("basic", 500, 10000)
    PRO = ("pro", 2000, 100000)
    ENTERPRISE = ("enterprise", 10000, 1000000)


class RateLimitEntry:
    """Rate limit tracking for an identifier."""
    
    def __init__(self, requests_per_minute: int, requests_per_day: int):
        self.requests_per_minute = requests_per_minute
        self.requests_per_day = requests_per_day
        
        self._minute_buckets: Dict[int, int] = {}
        self._daily_buckets: Dict[str, int] = {}
        self._total_requests = 0
    
    def check(self) -> Tuple[bool, Dict[str, Any]]:
        """Check if request is allowed."""
        now = time.time()
        current_minute = int(now // 60)
        current_day = datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y-%m-%d")
        
        # Check minute limit
        minute_count = self._minute_buckets.get(current_minute, 0)
        if minute_count >= self.requests_per_minute:
            retry_after = 60 - (now % 60)
            return False, {
                "limit": self.requests_per_minute,
                "remaining": 0,
                "retry_after": int(retry_after),
                "reset": int(retry_after)
            }
        
        # Check daily limit
        daily_count = self._daily_buckets.get(current_day, 0)
        if daily_count >= self.requests_per_day:
            # Reset at midnight UTC
            retry_after = 86400 - (now % 86400)
            return False, {
                "limit": self.requests_per_day,
                "remaining": 0,
                "retry_after": int(retry_after),
                "reset": int(retry_after)
            }
        
        # Update counters
        self._minute_buckets[current_minute] = minute_count + 1
        self._daily_buckets[current_day] = daily_count + 1
        self._total_requests += 1
        
        # Cleanup old buckets
        self._cleanup_old_buckets(current_minute, current_day)
        
        return True, {
            "limit": self.requests_per_minute,
            "remaining": self.requests_per_minute - minute_count - 1,
            "reset": 60 - int(now % 60)
        }
    
    def _cleanup_old_buckets(self, current_minute: int, current_day: str):
        """Remove old bucket entries."""
        # Keep only last 5 minutes
        cutoff_minute = current_minute - 5
        self._minute_buckets = {
            k: v for k, v in self._minute_buckets.items()
            if k > cutoff_minute
        }
        
        # Keep only last 7 days
        old_days = [
            d for d in self._daily_buckets.keys()
            if d < current_day
        ]
        for d in old_days[-7:]:
            del self._daily_buckets[d]


class RateLimitManager:
    """Manage rate limits for API keys and IPs."""
    
    def __init__(self, storage_dir: str = "integrations/api"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self._limits: Dict[str, RateLimitEntry] = {}
        self._lock = asyncio.Lock()
    
    async def get_limit(self, identifier: str) -> Tuple[int, int]:
        """Get rate limits for an identifier."""
        async with self._lock:
            if identifier not in self._limits:
                self._limits[identifier] = RateLimitEntry(100, 1000)
            
            entry = self._limits[identifier]
            return entry.requests_per_minute, entry.requests_per_day
    
    async def set_limit(
        self,
        identifier: str,
        requests_per_minute: int,
        requests_per_day: int
    ):
        """Set rate limits for an identifier."""
        async with self._lock:
            self._limits[identifier] = RateLimitEntry(
                requests_per_minute,
                requests_per_day
            )
    
    async def check(self, identifier: str) -> Tuple[bool, Dict[str, Any]]:
        """Check if request is allowed."""
        async with self._lock:
            if identifier not in self._limits:
                self._limits[identifier] = RateLimitEntry(100, 1000)
            
            return self._limits[identifier].check()
    
    async def get_usage(self, identifier: str) -> Dict[str, Any]:
        """Get usage statistics for an identifier."""
        async with self._lock:
            if identifier not in self._limits:
                return {"total_requests": 0, "errors": "Not found"}
            
            entry = self._limits[identifier]
            current_day = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
            
            return {
                "total_requests": entry._total_requests,
                "today_requests": entry._daily_buckets.get(current_day, 0),
                "requests_per_minute_limit": entry.requests_per_minute,
                "requests_per_day_limit": entry.requests_per_day,
            }


# ── API Key Management ─────────────────────────────────────────────────────────

class APIKey:
    """Represents an API key."""
    
    def __init__(
        self,
        key: str,
        name: str,
        tier: str = "free",
        permissions: Optional[List[str]] = None,
        rate_limit: Optional[int] = None,
        quota: Optional[int] = None,
        expires_at: Optional[float] = None
    ):
        self.key = key
        self.name = name
        self.tier = tier
        self.permissions = permissions or ["read"]
        self.rate_limit = rate_limit or 100
        self.quota = quota or 1000
        self.expires_at = expires_at
        
        self.created_at = time.time()
        self.last_used: Optional[float] = None
        self.use_count = 0
        self.metadata: Dict[str, Any] = {}


class APIGateway:
    """
    Production API Gateway with rate limiting, key management, and versioning.
    """
    
    def __init__(self, storage_dir: str = "integrations/api"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.rate_limit_manager = RateLimitManager(storage_dir)
        
        self._keys: Dict[str, APIKey] = {}
        self._request_logs: List[Dict[str, Any]] = []
        self._max_log_entries = 10000
        self._lock = asyncio.Lock()
        
        self._load_keys()
    
    def _load_keys(self):
        """Load API keys from storage."""
        keys_file = self.storage_dir / "keys.json"
        if keys_file.exists():
            try:
                with open(keys_file) as f:
                    data = json.load(f)
                    
                    for key_data in data.get("keys", []):
                        key = APIKey(
                            key=key_data["key"],
                            name=key_data["name"],
                            tier=key_data.get("tier", "free"),
                            permissions=key_data.get("permissions", ["read"]),
                            rate_limit=key_data.get("rate_limit", 100),
                            quota=key_data.get("quota", 1000),
                            expires_at=key_data.get("expires_at")
                        )
                        key.created_at = key_data.get("created_at", time.time())
                        key.last_used = key_data.get("last_used")
                        key.use_count = key_data.get("use_count", 0)
                        key.metadata = key_data.get("metadata", {})
                        self._keys[key.key] = key
                        
                        # Set rate limits
                        asyncio.create_task(self.rate_limit_manager.set_limit(
                            key.key,
                            key.rate_limit,
                            key.quota
                        ))
            except (json.JSONDecodeError, IOError):
                pass
    
    def _save_keys(self):
        """Save API keys to storage."""
        keys_file = self.storage_dir / "keys.json"
        try:
            keys_data = []
            for key in self._keys.values():
                keys_data.append({
                    "key": key.key,
                    "name": key.name,
                    "tier": key.tier,
                    "permissions": key.permissions,
                    "rate_limit": key.rate_limit,
                    "quota": key.quota,
                    "expires_at": key.expires_at,
                    "created_at": key.created_at,
                    "last_used": key.last_used,
                    "use_count": key.use_count,
                    "metadata": key.metadata,
                })
            
            with open(keys_file, 'w') as f:
                json.dump({"keys": keys_data}, f, indent=2)
        except IOError:
            pass
    
    # ── Key Generation ────────────────────────────────────────────────────────
    
    def generate_key(
        self,
        name: str,
        tier: str = "free",
        permissions: Optional[List[str]] = None,
        rate_limit: Optional[int] = None,
        quota: Optional[int] = None,
        expires_in_days: Optional[int] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Generate a new API key.
        
        Returns: (key, metadata)
        """
        key_str = f"aios_{secrets.token_urlsafe(32)}"
        
        tier_limits = {
            "free": (100, 1000),
            "basic": (500, 10000),
            "pro": (2000, 100000),
            "enterprise": (10000, 1000000),
        }
        
        default_rate, default_quota = tier_limits.get(tier, (100, 1000))
        
        api_key = APIKey(
            key=key_str,
            name=name,
            tier=tier,
            permissions=permissions or ["read"],
            rate_limit=rate_limit or default_rate,
            quota=quota or default_quota,
            expires_at=time.time() + (expires_in_days * 86400) if expires_in_days else None
        )
        
        self._keys[key_str] = api_key
        self._save_keys()
        
        asyncio.create_task(self.rate_limit_manager.set_limit(
            key_str,
            api_key.rate_limit,
            api_key.quota
        ))
        
        metadata = {
            "key": key_str,
            "name": name,
            "tier": tier,
            "permissions": api_key.permissions,
            "rate_limit": api_key.rate_limit,
            "quota": api_key.quota,
            "created_at": datetime.fromtimestamp(
                api_key.created_at, tz=timezone.utc
            ).isoformat(),
        }
        
        if expires_in_days:
            metadata["expires_at"] = datetime.fromtimestamp(
                api_key.expires_at, tz=timezone.utc
            ).isoformat()
        
        return key_str, metadata
    
    def validate_key(self, key: str) -> Tuple[bool, Optional[APIKey], Dict[str, Any]]:
        """
        Validate an API key.
        
        Returns: (is_valid, api_key, headers)
        """
        if key not in self._keys:
            return False, None, {"X-RateLimit-Limit": "0", "X-RateLimit-Remaining": "0"}
        
        api_key = self._keys[key]
        
        # Check expiration
        if api_key.expires_at and time.time() > api_key.expires_at:
            return False, None, {"X-Error": "API key expired"}
        
        # Update usage
        api_key.last_used = time.time()
        api_key.use_count += 1
        
        # Get rate limit info
        allowed, limit_info = asyncio.run(
            self.rate_limit_manager.check(key)
        )
        
        headers = {
            "X-RateLimit-Limit": str(limit_info["limit"]),
            "X-RateLimit-Remaining": str(limit_info["remaining"]),
            "X-RateLimit-Reset": str(limit_info["reset"]),
        }
        
        if not allowed:
            headers["Retry-After"] = str(limit_info.get("retry_after", 60))
            return False, api_key, headers
        
        return True, api_key, headers
    
    def revoke_key(self, key: str) -> bool:
        """Revoke an API key."""
        if key in self._keys:
            del self._keys[key]
            self._save_keys()
            return True
        return False
    
    def list_keys(self) -> List[Dict[str, Any]]:
        """List all API keys (without exposing secrets)."""
        return [
            {
                "name": k.name,
                "tier": k.tier,
                "permissions": k.permissions,
                "rate_limit": k.rate_limit,
                "quota": k.quota,
                "use_count": k.use_count,
                "created_at": datetime.fromtimestamp(
                    k.created_at, tz=timezone.utc
                ).isoformat(),
                "last_used": datetime.fromtimestamp(
                    k.last_used, tz=timezone.utc
                ).isoformat() if k.last_used else None,
                "expires_at": datetime.fromtimestamp(
                    k.expires_at, tz=timezone.utc
                ).isoformat() if k.expires_at else None,
            }
            for k in self._keys.values()
        ]
    
    def get_key_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """Get full metadata for a key."""
        if key not in self._keys:
            return None
        
        api_key = self._keys[key]
        return {
            "name": api_key.name,
            "tier": api_key.tier,
            "permissions": api_key.permissions,
            "rate_limit": api_key.rate_limit,
            "quota": api_key.quota,
            "use_count": api_key.use_count,
            "metadata": api_key.metadata,
            "created_at": datetime.fromtimestamp(
                api_key.created_at, tz=timezone.utc
            ).isoformat(),
            "last_used": datetime.fromtimestamp(
                api_key.last_used, tz=timezone.utc
            ).isoformat() if api_key.last_used else None,
        }
    
    # ── Request Logging ──────────────────────────────────────────────────────
    
    async def log_request(
        self,
        method: str,
        path: str,
        api_key: Optional[str],
        status_code: int,
        duration_ms: float,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log an API request."""
        async with self._lock:
            entry = {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "method": method,
                "path": path,
                "api_key": api_key[:8] if api_key else None,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "ip": ip,
                "user_agent": user_agent,
            }
            self._request_logs.append(entry)
            
            if len(self._request_logs) > self._max_log_entries:
                self._request_logs = self._request_logs[-self._max_log_entries:]
    
    def get_request_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent request logs."""
        return self._request_logs[-limit:]


# ── Global instance ───────────────────────────────────────────────────────────

api_gateway = APIGateway()
