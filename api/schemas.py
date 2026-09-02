from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    chat_id: str
    message: str
    trace_id: str


class SourceOut(BaseModel):
    source: str
    page: int
    block_type: str
    content: str
    similarity_score: Optional[float] = None


class ChatResponseOut(BaseModel):
    response: str
    route: str
    sources: list[SourceOut]
    sql: Optional[str] = None
    url: Optional[str] = None
    filename: Optional[str] = None
    trace_id: str
