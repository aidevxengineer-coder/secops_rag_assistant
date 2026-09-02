"""
Plain sync Redis client — used only for chat session storage (TTL'd
conversation history). NOT used for live trace events anymore — those go
through the in-process queue in event_bus.py instead.
"""

import redis
from .config import Config

_redis_client = None


def get_redis():
    global _redis_client
    if _redis_client is None:
        if not Config.REDIS_URL:
            raise EnvironmentError(
                "REDIS_URL not set in .env, e.g. redis://localhost:6379/0"
            )
        _redis_client = redis.from_url(Config.REDIS_URL, decode_responses=True)
    return _redis_client
