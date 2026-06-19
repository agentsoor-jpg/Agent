"""
integrations/webhook_manager.py - Webhook Integration System v7.0
Real webhook and API integration with signature verification, retry logic, and history.
"""

import asyncio
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import uuid

# ── Webhook Events ─────────────────────────────────────────────────────────────

class WebhookEventType(Enum):
    GITHUB_PUSH = "github.push"
    GITHUB_PR = "github.pull_request"
    GITHUB_ISSUE = "github.issues"
    GITHUB_COMMENT = "github.issue_comment"
    GITHUB_RELEASE = "github.release"
    GITHUB_WORKFLOW = "github.workflow_run"
    
    SLACK_MESSAGE = "slack.message"
    SLACK_INTERACTION = "slack.interaction"
    
    DISCORD_MESSAGE = "discord.message"
    DISCORD_INTERACTION = "discord.interaction"
    
    CUSTOM = "custom"


class WebhookStatus(Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"


# ── Webhook Delivery ───────────────────────────────────────────────────────────

class WebhookDelivery:
    """Represents a webhook delivery."""
    
    def __init__(
        self,
        webhook_id: str,
        url: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        event_type: str = "custom"
    ):
        self.id = str(uuid.uuid4())
        self.webhook_id = webhook_id
        self.url = url
        self.payload = payload
        self.headers = headers or {}
        self.event_type = event_type
        self.status = WebhookStatus.PENDING
        self.attempts = 0
        self.max_attempts = 5
        self.created_at = time.time()
        self.sent_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        self.response_status: Optional[int] = None
        self.response_body: Optional[str] = None
        self.error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "webhook_id": self.webhook_id,
            "url": self.url,
            "event_type": self.event_type,
            "status": self.status.value,
            "attempts": self.attempts,
            "created_at": self.created_at,
            "sent_at": self.sent_at,
            "completed_at": self.completed_at,
            "response_status": self.response_status,
            "error": self.error,
        }


class WebhookManager:
    """
    Production webhook manager with signature verification, retry logic, and history.
    """
    
    def __init__(self, storage_dir: str = "integrations/webhooks"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self._webhooks: Dict[str, Dict[str, Any]] = {}
        self._handlers: Dict[str, List[Callable]] = {}
        self._deliveries: Dict[str, List[WebhookDelivery]] = {}
        self._retry_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._retry_task: Optional[asyncio.Task] = None
        
        self._load_webhooks()
    
    def _load_webhooks(self):
        """Load webhooks from storage."""
        config_file = self.storage_dir / "webhooks.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    data = json.load(f)
                    self._webhooks = data.get("webhooks", {})
                    self._deliveries = data.get("deliveries", {})
            except (json.JSONDecodeError, IOError):
                self._webhooks = {}
                self._deliveries = {}
    
    def _save_webhooks(self):
        """Save webhooks to storage."""
        config_file = self.storage_dir / "webhooks.json"
        try:
            with open(config_file, 'w') as f:
                json.dump({
                    "webhooks": self._webhooks,
                }, f, indent=2)
        except IOError:
            pass
    
    # ── Webhook Registration ──────────────────────────────────────────────────
    
    def register_webhook(
        self,
        name: str,
        url: str,
        secret: Optional[str] = None,
        event_types: Optional[List[str]] = None,
        enabled: bool = True,
        headers: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Register a new webhook endpoint.
        
        Returns: webhook_id
        """
        webhook_id = str(uuid.uuid4())
        
        self._webhooks[webhook_id] = {
            "id": webhook_id,
            "name": name,
            "url": url,
            "secret": secret or secrets.token_urlsafe(32),
            "event_types": event_types or ["custom"],
            "enabled": enabled,
            "headers": headers or {},
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "stats": {
                "total_deliveries": 0,
                "successful_deliveries": 0,
                "failed_deliveries": 0,
            }
        }
        
        self._deliveries[webhook_id] = []
        self._save_webhooks()
        
        return webhook_id
    
    def update_webhook(self, webhook_id: str, updates: Dict[str, Any]) -> bool:
        """Update a webhook configuration."""
        if webhook_id not in self._webhooks:
            return False
        
        allowed_fields = {"name", "url", "enabled", "event_types", "headers", "metadata"}
        for key, value in updates.items():
            if key in allowed_fields:
                self._webhooks[webhook_id][key] = value
        
        self._save_webhooks()
        return True
    
    def delete_webhook(self, webhook_id: str) -> bool:
        """Delete a webhook."""
        if webhook_id in self._webhooks:
            del self._webhooks[webhook_id]
            if webhook_id in self._deliveries:
                del self._deliveries[webhook_id]
            self._save_webhooks()
            return True
        return False
    
    def get_webhook(self, webhook_id: str) -> Optional[Dict[str, Any]]:
        """Get webhook configuration."""
        return self._webhooks.get(webhook_id)
    
    def list_webhooks(self) -> List[Dict[str, Any]]:
        """List all webhooks."""
        return [
            {**wh, "secret": None}  # Don't expose secret in list
            for wh in self._webhooks.values()
        ]
    
    # ── Signature Verification ───────────────────────────────────────────────
    
    def verify_github_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify GitHub webhook signature."""
        if not signature:
            return False
        
        expected = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(f"sha256={expected}", signature)
    
    def verify_slack_signature(
        self,
        payload: bytes,
        timestamp: str,
        signature: str,
        secret: str
    ) -> bool:
        """Verify Slack webhook signature."""
        if not signature or not timestamp:
            return False
        
        # Check timestamp to prevent replay attacks
        if abs(time.time() - float(timestamp)) > 300:
            return False
        
        sig_basestring = f"v0:{timestamp}:{payload.decode()}"
        expected = "v0=" + hmac.new(
            secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)
    
    def verify_discord_signature(
        self,
        payload: bytes,
        signature: str,
        timestamp: str,
        secret: str
    ) -> bool:
        """Verify Discord webhook signature."""
        if not signature or not timestamp:
            return False
        
        expected = hmac.new(
            secret.encode(),
            f"{timestamp}{payload.decode()}".encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)
    
    def generate_signature(self, payload: str, secret: str, algorithm: str = "sha256") -> str:
        """Generate a webhook signature."""
        if algorithm == "sha256":
            return "sha256=" + hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
        raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    # ── Event Handlers ───────────────────────────────────────────────────────
    
    def register_handler(self, event_type: str, handler: Callable):
        """Register a handler for an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    async def handle_event(self, event_type: str, payload: Dict[str, Any]):
        """Handle an incoming webhook event."""
        handlers = self._handlers.get(event_type, [])
        handlers.extend(self._handlers.get("*", []))  # Also call wildcard handlers
        
        tasks = []
        for handler in handlers:
            if asyncio.iscoroutinefunction(handler):
                tasks.append(asyncio.create_task(handler(event_type, payload)))
            else:
                try:
                    handler(event_type, payload)
                except Exception as e:
                    pass
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    # ── Webhook Delivery ──────────────────────────────────────────────────────
    
    async def send_webhook(
        self,
        webhook_id: str,
        payload: Dict[str, Any],
        event_type: Optional[str] = None
    ) -> WebhookDelivery:
        """Send a webhook to a registered endpoint."""
        if webhook_id not in self._webhooks:
            raise ValueError(f"Webhook {webhook_id} not found")
        
        webhook = self._webhooks[webhook_id]
        
        delivery = WebhookDelivery(
            webhook_id=webhook_id,
            url=webhook["url"],
            payload=payload,
            headers=webhook.get("headers", {}),
            event_type=event_type or "custom"
        )
        
        self._deliveries.setdefault(webhook_id, []).append(delivery)
        
        await self._deliver_webhook(delivery)
        
        return delivery
    
    async def _deliver_webhook(self, delivery: WebhookDelivery):
        """Deliver a webhook with retry logic."""
        import httpx
        
        webhook = self._webhooks.get(delivery.webhook_id)
        if not webhook:
            delivery.status = WebhookStatus.FAILED
            delivery.error = "Webhook not found"
            return
        
        delivery.attempts += 1
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "AI-Engineering-OS/7.0 Webhook",
            "X-Webhook-ID": delivery.webhook_id,
            "X-Delivery-ID": delivery.id,
            **delivery.headers
        }
        
        if webhook.get("secret"):
            payload_str = json.dumps(delivery.payload)
            headers["X-Signature"] = self.generate_signature(payload_str, webhook["secret"])
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    delivery.url,
                    json=delivery.payload,
                    headers=headers
                )
                
                delivery.response_status = response.status_code
                delivery.response_body = response.text[:1000]  # Limit response storage
                delivery.sent_at = time.time()
                
                if 200 <= response.status_code < 300:
                    delivery.status = WebhookStatus.SENT
                    webhook["stats"]["successful_deliveries"] += 1
                else:
                    delivery.status = WebhookStatus.FAILED
                    webhook["stats"]["failed_deliveries"] += 1
                    delivery.error = f"HTTP {response.status_code}"
                
        except httpx.TimeoutException:
            delivery.status = WebhookStatus.FAILED
            delivery.error = "Request timed out"
        except httpx.RequestError as e:
            delivery.status = WebhookStatus.FAILED
            delivery.error = f"Request error: {str(e)}"
        except Exception as e:
            delivery.status = WebhookStatus.FAILED
            delivery.error = str(e)
        
        webhook["stats"]["total_deliveries"] += 1
        delivery.completed_at = time.time()
        self._save_webhooks()
        
        # Queue for retry if failed
        if delivery.status == WebhookStatus.FAILED and delivery.attempts < delivery.max_attempts:
            await self._retry_queue.put(delivery)
    
    async def _retry_worker(self):
        """Worker that processes retry queue with exponential backoff."""
        while self._running:
            try:
                delivery = await asyncio.wait_for(
                    self._retry_queue.get(),
                    timeout=1.0
                )
                
                # Calculate backoff: 2^attempt seconds, max 5 minutes
                backoff = min(300, 2 ** delivery.attempts)
                await asyncio.sleep(backoff)
                
                delivery.status = WebhookStatus.RETRYING
                await self._deliver_webhook(delivery)
                
            except asyncio.TimeoutError:
                continue
            except Exception:
                pass
    
    async def start(self):
        """Start the webhook manager."""
        self._running = True
        self._retry_task = asyncio.create_task(self._retry_worker())
    
    async def stop(self):
        """Stop the webhook manager."""
        self._running = False
        if self._retry_task:
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass
    
    # ── Webhook History ───────────────────────────────────────────────────────
    
    def get_deliveries(
        self,
        webhook_id: str,
        limit: int = 50,
        status: Optional[WebhookStatus] = None
    ) -> List[Dict[str, Any]]:
        """Get webhook delivery history."""
        if webhook_id not in self._deliveries:
            return []
        
        deliveries = self._deliveries[webhook_id]
        
        if status:
            deliveries = [d for d in deliveries if d.status == status]
        
        # Return most recent first
        deliveries = sorted(deliveries, key=lambda d: d.created_at, reverse=True)
        
        return [d.to_dict() for d in deliveries[:limit]]
    
    def get_stats(self, webhook_id: str) -> Optional[Dict[str, Any]]:
        """Get webhook statistics."""
        if webhook_id not in self._webhooks:
            return None
        
        return self._webhooks[webhook_id]["stats"]


# ── Pre-built Integration Helpers ─────────────────────────────────────────────

class GitHubWebhookHandler:
    """Helper for GitHub webhook events."""
    
    def __init__(self, webhook_manager: WebhookManager, secret: Optional[str] = None):
        self.webhook_manager = webhook_manager
        self.secret = secret or os.getenv("GITHUB_WEBHOOK_SECRET", "")
    
    def verify_and_parse(self, payload: bytes, signature: str, event: str) -> Optional[Dict[str, Any]]:
        """Verify GitHub signature and parse event."""
        if self.secret and not self.webhook_manager.verify_github_signature(
            payload, signature, self.secret
        ):
            return None
        
        try:
            data = json.loads(payload)
            return {
                "event_type": f"github.{event}",
                "payload": data,
                "action": data.get("action"),
                "repository": data.get("repository", {}).get("full_name"),
                "sender": data.get("sender", {}).get("login"),
            }
        except json.JSONDecodeError:
            return None
    
    async def handle(self, event_type: str, data: Dict[str, Any]):
        """Handle a GitHub event."""
        await self.webhook_manager.handle_event(event_type, data)


class SlackWebhookHandler:
    """Helper for Slack webhook events."""
    
    def __init__(self, webhook_manager: WebhookManager, signing_secret: Optional[str] = None):
        self.webhook_manager = webhook_manager
        self.signing_secret = signing_secret or os.getenv("SLACK_SIGNING_SECRET", "")
    
    def verify_and_parse(
        self,
        payload: bytes,
        timestamp: str,
        signature: str
    ) -> Optional[Dict[str, Any]]:
        """Verify Slack signature and parse event."""
        if self.signing_secret and not self.webhook_manager.verify_slack_signature(
            payload, timestamp, signature, self.signing_secret
        ):
            return None
        
        try:
            from urllib.parse import parse_qs
            data = parse_qs(payload.decode())
            return {
                "event_type": "slack.interaction",
                "payload": data,
                "team_id": data.get("team_id", [None])[0],
                "user_id": data.get("user_id", [None])[0],
            }
        except Exception:
            return None
    
    async def handle(self, event_type: str, data: Dict[str, Any]):
        """Handle a Slack event."""
        await self.webhook_manager.handle_event(event_type, data)


# ── Global instance ───────────────────────────────────────────────────────────

import os
webhook_manager = WebhookManager()
