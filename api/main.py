"""
FastAPI backend wrapping the LangGraph pipeline. Run from the project root
so the `graph` and `ingestion` packages resolve correctly.
"""

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os

from graph.build_graph import build_graph
from ingestion.config import Config
from .schemas import ChatRequest, ChatResponseOut, SourceOut
from ingestion.trace_store import start_trace, finish_trace
from fastapi import WebSocket, WebSocketDisconnect
from .ws_manager import manager
import asyncio
import json
import queue as queue_module
from ingestion.event_bus import create_queue, get_queue, remove_queue
from ingestion.live_events import publish_trace_event
from fastapi.responses import FileResponse
from pathlib import Path
# ingestion/report_cleanup.py
import time
import logging
from ingestion.config import Config
# main.py (or wherever your FastAPI app + lifespan is)
from contextlib import asynccontextmanager
from .auth.routes import router as auth_router
from .chat_history.routes import router as chat_history_router
from .auth.db import ensure_auth_tables
from .auth.admin.routes import router as admin_router
import json
from .chat_history import db as chat_db
from .auth.routes import get_current_user
from ingestion.trace_store import ensure_trace_tables

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_auth_tables()
    ensure_trace_tables()
    chat_db.ensure_chat_tables()
    cleanup_task = asyncio.create_task(sweep_expired_reports())
    yield
    cleanup_task.cancel()

app = FastAPI(title="SecOps Copilot API", lifespan=lifespan)

app.include_router(auth_router)
app.include_router(chat_history_router)
app.include_router(admin_router)

COLLECTION_NAME = "secops_kb"  # must match what you used during ingestion

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()  # compiled once, reused across requests
    return _graph


@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/chat", response_model=ChatResponseOut)
def chat(req: ChatRequest, user: dict = Depends(get_current_user)):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")

    chat_record = chat_db.get_chat(str(user["id"]), req.chat_id)
    if not chat_record:
        raise HTTPException(status_code=404, detail="Chat not found")

    message_count = chat_db.get_message_count(req.chat_id)
    already_summarized = chat_record.get("summarized_through", 0)

    # Only load MORE than the LLM window when there's a real unsummarized backlog
    # (i.e. summarizer_node genuinely has new work to do this turn). Otherwise
    # just load the normal small window — summarizer_node will no-op anyway.
    if message_count - already_summarized > Config.MAX_HISTORY_MESSAGES:
        load_limit = message_count - already_summarized  # exactly the unsummarized tail + recent window
    else:
        load_limit = Config.MAX_HISTORY_MESSAGES

    app_graph = get_graph()
    trace_id = req.trace_id

    create_queue(trace_id)
    start_trace(trace_id, req.message, chat_id=req.chat_id, user_id=str(user["id"]))

    # Load a window LARGER than HISTORY_LIMIT so summarizer_node has older
    # messages to fold in when this chat has grown past 10 turns
    past_messages = chat_db.get_messages(req.chat_id, limit=load_limit)
    conversation_history = [{"role": m["role"], "content": m["content"]} for m in past_messages]

    state = {
        "original_query": req.message,
        "trace_id": trace_id,
        "conversation_history": conversation_history,
        "history_summary": chat_record["history_summary"] or "",
        "collection_name": COLLECTION_NAME,
        "retry_count": 0,
        "max_retries": Config.MAX_RETRIES,
    }

    try:
        result = app_graph.invoke(state)
        if result.get("report_url"):
            publish_trace_event(trace_id, {
                "event": "report_ready",
                "url": result["report_url"],
                "filename": result["report_path"],
            })

    except Exception as e:
        publish_trace_event(trace_id, {"event": "trace_complete"})
        raise HTTPException(status_code=500, detail=f"Graph execution failed: {e}")

    finish_trace(trace_id, result.get("final_response", ""))
    publish_trace_event(trace_id, {"event": "trace_complete"})

    # persist both turns + updated rolling summary
    chat_db.add_message(req.chat_id, "user", req.message)
    chat_db.add_message(
        req.chat_id, "assistant", result.get("final_response", ""),
        route=result.get("route"),
        sources_json=json.dumps([
            {"source": d.metadata.get("source"), "page": d.metadata.get("page")}
            for d in (result.get("retrieved_docs") or [])
        ]) if result.get("retrieved_docs") else None,
        sql_text=result.get("table_sql"),
        report_url=result.get("report_url"),
    )
    new_total = message_count + 2  # this turn's user + assistant messages just added
    new_summarized_through = new_total - Config.MAX_HISTORY_MESSAGES if new_total > Config.MAX_HISTORY_MESSAGES else already_summarized
    chat_db.touch_chat(
            req.chat_id,
            history_summary=result.get("history_summary"),
            summarized_through=max(new_summarized_through, already_summarized),
    )

    sources_out = [
        SourceOut(
            source=doc.metadata.get("source", "unknown"), page=doc.metadata.get("page", 0),
            block_type=doc.metadata.get("block_type", "text"), content=doc.page_content,
            similarity_score=doc.metadata.get("similarity_score"),
        )
        for doc in (result.get("retrieved_docs") or [])
    ]

    return ChatResponseOut(
        response=result.get("final_response", ""), route=result.get("route", "none"),
        sources=sources_out, sql=result.get("table_sql"),
        url=result.get("report_url"), filename=result.get("report_path"),
        trace_id=trace_id,
    )


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "subscribe" and msg.get("trace_id"):
                asyncio.create_task(_drain_queue(session_id, msg["trace_id"]))
    except WebSocketDisconnect:
        manager.disconnect(session_id)


async def _drain_queue(session_id: str, trace_id: str):
    # subscribe might arrive slightly before /chat creates the queue — wait briefly
    for _ in range(50):
        q = get_queue(trace_id)
        if q:
            break
        await asyncio.sleep(0.1)
    else:
        return

    while True:
        try:
            event = q.get_nowait()
        except queue_module.Empty:
            await asyncio.sleep(0.05)
            continue
        await manager.send_event(session_id, event)
        if event.get("event") == "trace_complete":
            remove_queue(trace_id)
            return

@app.get("/api/reports/{filename}")
def download_report(filename: str):
    safe_name = Path(filename).name  # strips any ../ path traversal attempt
    if safe_name != filename or not filename.startswith("secops_report_") or not filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = Config.REPORTS_DIR / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=safe_name,  # sets Content-Disposition: attachment → browser downloads, doesn't open inline
    )

logger = logging.getLogger(__name__)
REPORT_TTL_SECONDS = 60 * 60 * 2  # delete anything older than 2 hours — tune as needed
SWEEP_INTERVAL_SECONDS = 60 * 15  # check every 15 min

async def sweep_expired_reports():
    while True:
        try:
            now = time.time()
            for f in Config.REPORTS_DIR.glob("secops_report_*.pdf"):
                if now - f.stat().st_mtime > REPORT_TTL_SECONDS:
                    f.unlink(missing_ok=True)
                    logger.info(f"[report_cleanup] deleted expired report: {f.name}")
        except Exception as e:
            logger.error(f"[report_cleanup] sweep failed: {e}")
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)