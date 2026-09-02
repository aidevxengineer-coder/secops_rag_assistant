"""
Publishes live trace/LLM-call events to the in-process event bus.
No Redis involved in this path anymore — see event_bus.py.
"""

from .event_bus import push_event


def publish_trace_event(trace_id: str, event: dict):
    push_event(trace_id, "events", event)


def publish_llm_call_event(trace_id: str, event: dict):
    push_event(trace_id, "llm_calls", event)
