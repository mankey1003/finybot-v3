import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter()


class FrontendError(BaseModel):
    message: str
    stack: Optional[str] = None
    url: Optional[str] = None
    user_agent: Optional[str] = None


@router.post("", status_code=204)
async def log_frontend_error(error: FrontendError, request: Request):
    """
    Sink for frontend JavaScript errors.
    Frontend sends unhandled errors here via window.onerror / unhandledrejection.
    They are logged as structured JSON to Cloud Logging alongside backend errors.
    """
    logger.error(
        "frontend_error",
        extra={
            "message": error.message,
            "stack": error.stack,
            "url": error.url,
            "user_agent": error.user_agent,
            "client_ip": request.client.host if request.client else None,
        },
    )
