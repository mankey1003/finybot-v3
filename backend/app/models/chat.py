from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ToolCallData(BaseModel):
    name: str
    arguments: dict
    result: Optional[str] = None


class ChatMessageResponse(BaseModel):
    id: str
    role: str  # "user" | "assistant"
    content: Optional[str] = None
    tool_calls: Optional[list[ToolCallData]] = None
    created_at: Optional[datetime] = None


class ChatResponse(BaseModel):
    id: str
    title: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ChatListResponse(BaseModel):
    chats: list[ChatResponse]


class SendMessageRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
