"""
In-process event bus bridging the sync graph-execution thread to the async
WebSocket endpoint — replaces Redis Streams entirely for the live push path.
Redis Streams' blocking XREAD was the wrong tool here (caused timeout errors
under normal LLM latency). Postgres (trace_store.py) already durably logs
every event for later "fetch it all at once" use — no need for a second
storage layer just for that.
"""

import queue
import threading

_lock = threading.Lock()
_queues: dict[str, queue.Queue] = {}


def create_queue(trace_id: str) -> queue.Queue:
    q = queue.Queue()
    with _lock:
        _queues[trace_id] = q
    return q


def get_queue(trace_id: str) -> queue.Queue | None:
    with _lock:
        return _queues.get(trace_id)


def remove_queue(trace_id: str):
    with _lock:
        _queues.pop(trace_id, None)


def push_event(trace_id: str, channel: str, event: dict):
    q = get_queue(trace_id)
    if q:
        q.put({**event, "_channel": channel})
