"""
Chat session storage in Redis with a TTL — not permanent (matches what you
want: no Postgres persistence), but survives briefly across backend restarts
and works correctly if you ever run multiple FastAPI workers.
"""

import json
from ingestion.redis_client import get_redis

SESSION_TTL_SECONDS = 3600  # 1 hour


def _key(session_id: str) -> str:
    return f"chat_session:{session_id}"


def get_session(session_id: str) -> dict:
    r = get_redis()
    raw = r.get(_key(session_id))
    if raw:
        return json.loads(raw)
    return {"conversation_history": [], "history_summary": ""}


def update_session(session_id: str, conversation_history: list, history_summary: str):
    r = get_redis()
    r.set(
        _key(session_id),
        json.dumps(
            {
                "conversation_history": conversation_history,
                "history_summary": history_summary,
            }
        ),
        ex=SESSION_TTL_SECONDS,
    )
