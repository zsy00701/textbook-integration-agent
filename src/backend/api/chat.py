"""多轮对话 + 整合反馈 API。"""
from __future__ import annotations
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.chat.feedback import handle_user_message

router = APIRouter()


class ChatReq(BaseModel):
    message: str
    session_id: str | None = None


@router.post("/chat")
def chat(req: ChatReq) -> dict:
    sid = req.session_id or uuid.uuid4().hex[:12]
    if not req.message.strip():
        raise HTTPException(400, "消息不能为空")
    return handle_user_message(sid, req.message).model_dump()
