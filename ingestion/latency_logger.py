"""
Lightweight latency logger. Every pipeline stage gets timed and appended
to logs/latency.jsonl as a structured record. This is what your dashboard
/ LangSmith comparison will read from later.
"""

import time
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from .config import Config


def _ensure_log_dir():
    os.makedirs(Config.LOG_DIR, exist_ok=True)


def log_event(stage: str, duration_ms: float, doc_id: str, meta: dict | None = None):
    _ensure_log_dir()
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "doc_id": doc_id,
        "stage": stage,
        "duration_ms": round(duration_ms, 2),
        "meta": meta or {},
    }
    with open(Config.LATENCY_LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")


@contextmanager
def timed_stage(stage: str, doc_id: str, meta: dict | None = None):
    """
    Usage:
        with timed_stage("pdf_parse", doc_id="report.pdf"):
            ... do work ...
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        log_event(stage, duration_ms, doc_id, meta)
        print(f"[latency] {stage:<20} {duration_ms:>8.2f} ms  (doc={doc_id})")
