import json
import logging
import uuid
from typing import Generator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.middleware.auth_middleware import get_current_uid
from app.models.chat import ChatListResponse, ChatResponse, ChatMessageResponse, SendMessageRequest, ToolCallData
from app.services import firestore_service
from app.services.chat_agent_service import generate_chat_title, run_agent_stream

logger = logging.getLogger(__name__)
router = APIRouter()


def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


@router.get("", response_model=ChatListResponse)
def list_chats(uid: str = Depends(get_current_uid)):
    chats = firestore_service.get_chats(uid)
    return ChatListResponse(
        chats=[
            ChatResponse(
                id=c["id"],
                title=c.get("title", "New Chat"),
                created_at=c.get("createdAt"),
                updated_at=c.get("updatedAt"),
            )
            for c in chats
        ]
    )


@router.delete("/{chat_id}")
def delete_chat(chat_id: str, uid: str = Depends(get_current_uid)):
    chat = firestore_service.get_chat(uid, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    firestore_service.delete_chat(uid, chat_id)
    return {"detail": "Chat deleted"}


@router.get("/{chat_id}/messages", response_model=list[ChatMessageResponse])
def get_messages(chat_id: str, uid: str = Depends(get_current_uid)):
    chat = firestore_service.get_chat(uid, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    messages = firestore_service.get_messages(uid, chat_id)
    return [
        ChatMessageResponse(
            id=m["id"],
            role=m.get("role", "user"),
            content=m.get("content"),
            tool_calls=[ToolCallData(**tc) for tc in m["toolCalls"]] if m.get("toolCalls") else None,
            created_at=m.get("createdAt"),
        )
        for m in messages
    ]


@router.post("/send")
def send_message(body: SendMessageRequest, uid: str = Depends(get_current_uid)):
    chat_id = body.conversation_id
    is_new_chat = chat_id is None

    if is_new_chat:
        chat_id = str(uuid.uuid4())
        title = body.message[:50]
        firestore_service.create_chat(uid, chat_id, title)
    else:
        chat = firestore_service.get_chat(uid, chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

    # Persist user message
    firestore_service.add_message(uid, chat_id, {
        "role": "user",
        "content": body.message,
        "toolCalls": None,
    })

    # Load conversation history (excluding the message we just added — it's in the stream input)
    history = firestore_service.get_messages(uid, chat_id)
    # Remove the last message (the one we just added) since we pass it directly
    history_for_agent = history[:-1] if history else []

    def event_stream() -> Generator[str, None, None]:
        # First event: send chat_id so frontend knows the conversation
        yield _sse_event("chat_id", {"chat_id": chat_id})

        assistant_content = ""
        assistant_tool_calls = []

        try:
            for event_str in run_agent_stream(uid, body.message, history_for_agent):
                yield event_str

                # Parse event to accumulate assistant message data
                if event_str.startswith("event: message\n"):
                    data_line = event_str.split("data: ", 1)[1].split("\n")[0]
                    data = json.loads(data_line)
                    assistant_content = data.get("content", "")
                    assistant_tool_calls = data.get("tool_calls", [])

        except Exception as e:
            logger.error("stream_error", extra={"error": str(e)}, exc_info=True)
            yield _sse_event("error", {"message": "An error occurred while processing your request."})
        finally:
            # Persist assistant message
            if assistant_content or assistant_tool_calls:
                firestore_service.add_message(uid, chat_id, {
                    "role": "assistant",
                    "content": assistant_content,
                    "toolCalls": assistant_tool_calls if assistant_tool_calls else None,
                })
                firestore_service.touch_chat(uid, chat_id)

            # Generate a better title for new chats
            if is_new_chat:
                try:
                    title = generate_chat_title(body.message)
                    firestore_service.update_chat_title(uid, chat_id, title)
                except Exception:
                    pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
