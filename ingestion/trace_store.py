"""
Durable trace storage in Postgres — the queryable record of every run.
Mirrors table_store.py's engine/connection pattern.
"""

import json
from datetime import datetime, timezone
from sqlalchemy import text
from .table_store import get_engine  # reuse the same Postgres engine


def ensure_trace_tables():
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS traces (
                trace_id UUID PRIMARY KEY,
                started_at TIMESTAMPTZ,
                finished_at TIMESTAMPTZ,
                user_query TEXT,
                final_response TEXT,
                chat_id UUID,
                user_id UUID
            )
        """))
        # for existing DBs created before these columns existed:
        conn.execute(text("ALTER TABLE traces ADD COLUMN IF NOT EXISTS chat_id UUID"))
        conn.execute(text("ALTER TABLE traces ADD COLUMN IF NOT EXISTS user_id UUID"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_traces_user ON traces(user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_llm_calls_created ON llm_calls(created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_llm_calls_node ON llm_calls(node_name)"))


def start_trace(trace_id: str, user_query: str, chat_id: str = None, user_id: str = None):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO traces (trace_id, started_at, user_query, chat_id, user_id)
            VALUES (:trace_id, :started_at, :user_query, :chat_id, :user_id)
        """), {
            "trace_id": trace_id, "started_at": datetime.now(timezone.utc),
            "user_query": user_query, "chat_id": chat_id, "user_id": user_id,
        })


def finish_trace(trace_id: str, final_response: str):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text("""
            UPDATE traces SET finished_at = :finished_at, final_response = :final_response
            WHERE trace_id = :trace_id
        """),
            {
                "finished_at": datetime.now(timezone.utc),
                "final_response": final_response,
                "trace_id": trace_id,
            },
        )


def save_trace_event(
    trace_id: str,
    event_type: str,
    node_name: str,
    duration_ms: float | None = None,
    payload: dict | None = None,
):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text("""
            INSERT INTO trace_events (trace_id, timestamp, event_type, node_name, duration_ms, payload)
            VALUES (:trace_id, :timestamp, :event_type, :node_name, :duration_ms, :payload)
        """),
            {
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc),
                "event_type": event_type,
                "node_name": node_name,
                "duration_ms": duration_ms,
                "payload": json.dumps(payload or {}, default=str),
            },
        )


def save_llm_call(
    trace_id: str,
    node_name: str,
    model: str,
    prompt: str,
    response: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    latency_ms: float,
):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text("""
            INSERT INTO llm_calls (trace_id, node_name, model, prompt, response,
                                    prompt_tokens, completion_tokens, total_tokens, latency_ms, created_at)
            VALUES (:trace_id, :node_name, :model, :prompt, :response,
                    :prompt_tokens, :completion_tokens, :total_tokens, :latency_ms, :created_at)
        """),
            {
                "trace_id": trace_id,
                "node_name": node_name,
                "model": model,
                "prompt": prompt[:5000],
                "response": response[:5000],  # cap length, these can get long
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "latency_ms": latency_ms,
                "created_at": datetime.now(timezone.utc),
            },
        )


def get_trace_events(trace_id: str) -> list[dict]:
    engine = get_engine()
    with engine.begin() as conn:
        rows = (
            conn.execute(
                text("SELECT * FROM trace_events WHERE trace_id = :tid ORDER BY id"),
                {"tid": trace_id},
            )
            .mappings()
            .all()
        )
    return [dict(r) for r in rows]

def get_latency_percentiles(hours: int = 24):
    engine = get_engine()
    with engine.begin() as conn:
        rows = conn.execute(text(f"""
            SELECT node_name,
                   COUNT(*) AS call_count,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) AS p50,
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95,
                   AVG(latency_ms) AS avg_ms
            FROM llm_calls
            WHERE created_at > now() - interval '{hours} hours' AND total_tokens > 0
            GROUP BY node_name ORDER BY p95 DESC
        """)).mappings().all()
    return [dict(r) for r in rows]


def get_failure_rates(hours: int = 24):
    engine = get_engine()
    with engine.begin() as conn:
        rows = conn.execute(text(f"""
            SELECT node_name,
                   COUNT(*) FILTER (WHERE total_tokens = 0) AS failures,
                   COUNT(*) AS total_attempts,
                   ROUND(100.0 * COUNT(*) FILTER (WHERE total_tokens = 0) / COUNT(*), 1) AS failure_pct
            FROM llm_calls
            WHERE created_at > now() - interval '{hours} hours'
            GROUP BY node_name ORDER BY failure_pct DESC
        """)).mappings().all()
    return [dict(r) for r in rows]


def get_token_usage_by_model(hours: int = 24):
    engine = get_engine()
    with engine.begin() as conn:
        rows = conn.execute(text(f"""
            SELECT model,
                   SUM(prompt_tokens) AS total_input_tokens,
                   SUM(completion_tokens) AS total_output_tokens,
                   COUNT(*) FILTER (WHERE total_tokens > 0) AS successful_calls
            FROM llm_calls
            WHERE created_at > now() - interval '{hours} hours'
            GROUP BY model
        """)).mappings().all()
    return [dict(r) for r in rows]


def get_usage_by_user(hours: int = 24, limit: int = 20):
    engine = get_engine()
    with engine.begin() as conn:
        rows = conn.execute(text(f"""
            SELECT t.user_id,
                   COUNT(DISTINCT t.trace_id) AS request_count,
                   SUM(l.total_tokens) AS total_tokens
            FROM traces t
            JOIN llm_calls l ON l.trace_id = t.trace_id
            WHERE t.started_at > now() - interval '{hours} hours' AND t.user_id IS NOT NULL
            GROUP BY t.user_id ORDER BY total_tokens DESC LIMIT {limit}
        """)).mappings().all()
    return [dict(r) for r in rows]

def get_node_wall_latency(hours: int = 24):
    """
    Full node latency INCLUDING retries/backoff/fallback attempts — this is
    what the user actually experienced, unlike llm_calls latency which only
    reflects the final successful attempt's own duration.
    """
    engine = get_engine()
    with engine.begin() as conn:
        rows = conn.execute(text(f"""
            SELECT node_name,
                   COUNT(*) AS call_count,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY duration_ms) AS p50,
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95,
                   AVG(duration_ms) AS avg_ms,
                   MAX(duration_ms) AS max_ms
            FROM trace_events
            WHERE duration_ms IS NOT NULL AND timestamp > now() - interval '{hours} hours'
            GROUP BY node_name ORDER BY p95 DESC
        """)).mappings().all()
    return [dict(r) for r in rows]
