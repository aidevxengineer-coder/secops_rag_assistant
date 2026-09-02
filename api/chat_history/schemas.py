from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CreateProjectRequest(BaseModel):
    name: str

class CreateChatRequest(BaseModel):
    project_id: Optional[str] = None
    title: Optional[str] = "New Chat"

class RenameChatRequest(BaseModel):
    title: str

class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    route: Optional[str] = None
    sql_text: Optional[str] = None
    report_url: Optional[str] = None
    created_at: datetime

class ChatOut(BaseModel):
    id: str
    project_id: Optional[str] = None
    title: str
    created_at: datetime
    updated_at: datetime

class ProjectOut(BaseModel):
    id: str
    name: str
    created_at: datetime