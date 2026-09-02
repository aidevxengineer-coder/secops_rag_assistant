from fastapi import APIRouter, Depends, HTTPException
from .schemas import CreateProjectRequest, CreateChatRequest, RenameChatRequest, ChatOut, ProjectOut, MessageOut
from . import db
from ..auth.routes import get_current_user

router = APIRouter(tags=["chat_history"])


@router.post("/projects", response_model=ProjectOut)
def create_project(req: CreateProjectRequest, user: dict = Depends(get_current_user)):
    p = db.create_project(str(user["id"]), req.name)
    return ProjectOut(id=str(p["id"]), name=p["name"], created_at=p["created_at"])


@router.get("/projects")
def list_projects(user: dict = Depends(get_current_user)):
    return db.list_projects(str(user["id"]))


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, user: dict = Depends(get_current_user)):
    db.delete_project(str(user["id"]), project_id)
    return {"status": "deleted"}


@router.post("/chats", response_model=ChatOut)
def create_chat(req: CreateChatRequest, user: dict = Depends(get_current_user)):
    c = db.create_chat(str(user["id"]), req.project_id, req.title)
    return ChatOut(id=str(c["id"]), project_id=str(c["project_id"]) if c["project_id"] else None,
                    title=c["title"], created_at=c["created_at"], updated_at=c["updated_at"])


@router.get("/chats")
def list_chats(project_id: str = None, user: dict = Depends(get_current_user)):
    return db.list_chats(str(user["id"]), project_id)


@router.get("/chats/{chat_id}/messages")
def get_chat_messages(chat_id: str, user: dict = Depends(get_current_user)):
    chat = db.get_chat(str(user["id"]), chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return db.get_messages(chat_id, limit=30)


@router.patch("/chats/{chat_id}")
def rename_chat(chat_id: str, req: RenameChatRequest, user: dict = Depends(get_current_user)):
    chat = db.get_chat(str(user["id"]), chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    db.rename_chat(str(user["id"]), chat_id, req.title)
    return {"status": "renamed"}


@router.delete("/chats/{chat_id}")
def delete_chat(chat_id: str, user: dict = Depends(get_current_user)):
    db.delete_chat(str(user["id"]), chat_id)
    return {"status": "deleted"}