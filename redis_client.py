import time
from typing import Any, Callable

import redis

from config import settings


class InMemoryPipeline:
    def __init__(self, client: "InMemoryRedis"):
        self.client = client
        self.commands: list[Callable[[], Any]] = []

    def incr(self, key: str):
        self.commands.append(lambda: self.client.incr(key))
        return self

    def expire(self, key: str, seconds: int):
        self.commands.append(lambda: self.client.expire(key, seconds))
        return self

    def execute(self):
        return [command() for command in self.commands]


class InMemoryRedis:
    """Small Redis-compatible client for local development and tests."""

    def __init__(self):
        self._values: dict[str, Any] = {}
        self._expires: dict[str, float] = {}

    def _purge_if_expired(self, key: str):
        expires_at = self._expires.get(key)
        if expires_at is not None and expires_at <= time.time():
            self._values.pop(key, None)
            self._expires.pop(key, None)

    def exists(self, key: str):
        self._purge_if_expired(key)
        return 1 if key in self._values else 0

    def setex(self, key: str, seconds: int, value: Any):
        self._values[key] = str(value)
        self._expires[key] = time.time() + seconds
        return True

    def set(self, key: str, value: Any):
        self._values[key] = str(value)
        self._expires.pop(key, None)
        return True

    def get(self, key: str):
        self._purge_if_expired(key)
        value = self._values.get(key)
        return None if isinstance(value, (dict, list)) else value

    def incr(self, key: str):
        self._purge_if_expired(key)
        value = int(self._values.get(key) or 0) + 1
        self._values[key] = str(value)
        return value

    def expire(self, key: str, seconds: int):
        if key not in self._values:
            return False
        self._expires[key] = time.time() + seconds
        return True

    def ttl(self, key: str):
        self._purge_if_expired(key)
        if key not in self._values:
            return -2
        if key not in self._expires:
            return -1
        return max(0, int(self._expires[key] - time.time()))

    def pipeline(self):
        return InMemoryPipeline(self)

    def hgetall(self, key: str):
        self._purge_if_expired(key)
        value = self._values.get(key)
        return dict(value) if isinstance(value, dict) else {}

    def hset(self, key: str, mapping: dict[str, Any]):
        self._purge_if_expired(key)
        current = self._values.get(key)
        if not isinstance(current, dict):
            current = {}
        current.update({k: str(v) for k, v in mapping.items()})
        self._values[key] = current
        return len(mapping)

    def lpush(self, key: str, value: Any):
        self._purge_if_expired(key)
        current = self._values.get(key)
        if not isinstance(current, list):
            current = []
        current.insert(0, str(value))
        self._values[key] = current
        return len(current)

    def ltrim(self, key: str, start: int, end: int):
        self._purge_if_expired(key)
        current = self._values.get(key)
        if not isinstance(current, list):
            return True
        stop = None if end == -1 else end + 1
        self._values[key] = current[start:stop]
        return True

    def lrange(self, key: str, start: int, end: int):
        self._purge_if_expired(key)
        current = self._values.get(key)
        if not isinstance(current, list):
            return []
        stop = None if end == -1 else end + 1
        return current[start:stop]


if settings.REDIS_URL.startswith("memory://"):
    redis_client = InMemoryRedis()
else:
    redis_pool = redis.ConnectionPool.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        max_connections=20,
    )
    redis_client = redis.Redis(connection_pool=redis_pool)


def get_redis():
    """Get Redis-compatible client."""
    return redis_client
