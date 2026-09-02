"""Tracks one active WebSocket per session_id."""

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active[session_id] = websocket

    def disconnect(self, session_id: str):
        self.active.pop(session_id, None)

    async def send_event(self, session_id: str, event: dict):
        ws = self.active.get(session_id)
        if ws:
            try:
                await ws.send_json(event)
            except Exception:
                pass  # connection likely closed, drop silently


manager = ConnectionManager()
