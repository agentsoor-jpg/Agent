"""Redis Pub/Sub helper (simple wrapper)"""
import os
import threading
import time
from loguru import logger
import redis

class RedisPubSub:
    def __init__(self, url: str = None):
        self.url = url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            self.client = redis.from_url(self.url, socket_timeout=2)
            self.client.ping()
            self.pubsub = self.client.pubsub(ignore_subscribe_messages=True)
            logger.info("RedisPubSub successfully connected to Redis server.")
        except Exception as e:
            logger.warning(f"RedisPubSub: Redis unavailable ({e}). Using simulated pub/sub fallback.")
            self.client = None
            self.pubsub = None
        
        self.listeners = {}
        self._listener_thread = None

    def publish(self, channel: str, message: str):
        if self.client:
            try:
                return self.client.publish(channel, message)
            except Exception as e:
                logger.error(f"Redis publish failed: {e}")
        
        # Local simulated fallback
        logger.info(f"[Simulated Pub/Sub Channel '{channel}'] Published: {message}")
        if channel in self.listeners:
            try:
                self.listeners[channel](channel, message)
            except Exception as e:
                logger.exception("Error in local pubsub fallback callback")
        return 1

    def subscribe(self, channel: str, callback):
        self.listeners[channel] = callback
        if self.pubsub:
            try:
                self.pubsub.subscribe(channel)
                if self._listener_thread is None:
                    self._start_listener()
            except Exception as e:
                logger.error(f"Redis subscribe failed: {e}. Falling back to simulated local registration.")
                self.pubsub = None

    def _start_listener(self):
        if not self.pubsub:
            return
            
        def run():
            logger.info("Starting Redis listener thread")
            for message in self.pubsub.listen():
                if message is None:
                    time.sleep(0.1)
                    continue
                chan = message.get("channel")
                data = message.get("data")
                if isinstance(chan, bytes):
                    chan = chan.decode()
                if isinstance(data, bytes):
                    data = data.decode()
                cb = self.listeners.get(chan)
                if cb:
                    try:
                        cb(chan, data)
                    except Exception as e:
                        logger.exception("Error in pubsub callback")
        self._listener_thread = threading.Thread(target=run, daemon=True)
        self._listener_thread.start()
