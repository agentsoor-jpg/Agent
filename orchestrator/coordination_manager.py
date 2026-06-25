"""
Coordination Manager - Manages task/file ownership to prevent conflicts.
Supports Redis-backed persistent locking with fallback to in-memory store.
"""

import os
from typing import Dict, Optional
import redis
from loguru import logger

class CoordinationManager:
    def __init__(self):
        self._local_tasks: Dict[str, str] = {}  # task_id -> agent
        self._local_files: Dict[str, str] = {}  # file_path -> agent
        self.redis_client = None

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            self.redis_client = redis.from_url(redis_url, socket_timeout=2)
            self.redis_client.ping()
            logger.info("CoordinationManager: Connected to Redis for persistent locks.")
        except Exception as e:
            logger.warning(f"CoordinationManager: Redis unavailable ({e}). Falling back to in-memory locking.")
            self.redis_client = None

    def claim_task(self, task_id: str, agent: str) -> bool:
        if self.redis_client:
            try:
                # Set if not exists (NX) with 300 seconds expiration (EX)
                success = self.redis_client.set(f"lock:task:{task_id}", agent, nx=True, ex=300)
                return bool(success)
            except Exception as e:
                logger.error(f"Redis claim_task error: {e}")
        
        # Local fallback
        if task_id in self._local_tasks:
            return False
        self._local_tasks[task_id] = agent
        return True

    def release_task(self, task_id: str):
        if self.redis_client:
            try:
                self.redis_client.delete(f"lock:task:{task_id}")
                return
            except Exception as e:
                logger.error(f"Redis release_task error: {e}")
        
        self._local_tasks.pop(task_id, None)

    def claim_file(self, file_path: str, agent: str) -> bool:
        normalized_path = os.path.normpath(file_path)
        if self.redis_client:
            try:
                success = self.redis_client.set(f"lock:file:{normalized_path}", agent, nx=True, ex=300)
                return bool(success)
            except Exception as e:
                logger.error(f"Redis claim_file error: {e}")

        # Local fallback
        if normalized_path in self._local_files:
            return False
        self._local_files[normalized_path] = agent
        return True

    def release_file(self, file_path: str):
        normalized_path = os.path.normpath(file_path)
        if self.redis_client:
            try:
                self.redis_client.delete(f"lock:file:{normalized_path}")
                return
            except Exception as e:
                logger.error(f"Redis release_file error: {e}")

        self._local_files.pop(normalized_path, None)

    def can_edit_file(self, file_path: str, agent: str) -> bool:
        normalized_path = os.path.normpath(file_path)
        owner = self.get_file_owner(normalized_path)
        return owner is None or owner == agent

    def get_file_owner(self, file_path: str) -> Optional[str]:
        normalized_path = os.path.normpath(file_path)
        if self.redis_client:
            try:
                owner = self.redis_client.get(f"lock:file:{normalized_path}")
                if owner:
                    return owner.decode('utf-8') if isinstance(owner, bytes) else str(owner)
            except Exception as e:
                logger.error(f"Redis get_file_owner error: {e}")
        
        return self._local_files.get(normalized_path)
