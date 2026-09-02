"""
Wraps every graph node with timing + Postgres trace_events + Redis live push.
Deliberately does NOT deepcopy full state (Documents aren't cheaply
serializable and it's not worth the latency) — logs each node's own output
payload instead, which is already the meaningful part.
"""

import time
import functools
from ingestion.trace_store import save_trace_event
from ingestion.live_events import publish_trace_event


def trace_node(node_name: str):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(state):
            trace_id = state.get("trace_id")
            start = time.perf_counter()

            result = func(state)

            duration_ms = (time.perf_counter() - start) * 1000

            # Keep the payload JSON-safe: drop non-serializable objects
            # (retrieved_docs are LangChain Documents — summarize instead)
            payload = {}
            for k, v in result.items():
                if k == "retrieved_docs":
                    payload["retrieved_count"] = len(v)
                    payload["sources"] = [d.metadata.get("source") for d in v]
                elif k == "table_rows":
                    payload["row_count"] = len(v)
                else:
                    payload[k] = v

            if trace_id:
                save_trace_event(
                    trace_id, "node_complete", node_name, duration_ms, payload
                )
                publish_trace_event(
                    trace_id,
                    {
                        "event": "node_complete",
                        "node": node_name,
                        "duration_ms": round(duration_ms, 1),
                        "payload": payload,
                    },
                )

            return result

        return wrapper

    return decorator
