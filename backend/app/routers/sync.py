from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from app.middleware.auth_middleware import get_current_uid
from app.services import firestore_service
from app.services.sync_service import run_sync

logger = logging.getLogger(__name__)
router = APIRouter()


class SyncResponse(BaseModel):
    job_id: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str  # pending | processing | done | failed
    results: dict | None = None
    error_reason: str | None = None


@router.post("", response_model=SyncResponse)
def trigger_sync(
    background_tasks: BackgroundTasks,
    uid: str = Depends(get_current_uid),
):
    """
    Trigger a Gmail sync for the authenticated user.
    Called by the "Refresh" button on the frontend.

    Returns immediately with a job_id.
    The frontend should poll GET /api/sync/status/{job_id} every 3 seconds
    until status is "done" or "failed".

    The actual sync (Gmail fetch → PDF decrypt → Gemini extract → Firestore write)
    runs in a background thread via FastAPI BackgroundTasks so the response is instant.
    """
    user = firestore_service.get_user(uid)
    if not user or not user.get("gmailConnected"):
        raise HTTPException(
            status_code=400,
            detail="Gmail not connected. Complete Gmail authorization first.",
        )

    cards = firestore_service.get_card_providers(uid)
    if not cards:
        raise HTTPException(
            status_code=400,
            detail="No card providers configured. Add at least one card first.",
        )

    job_id = str(uuid.uuid4())
    firestore_service.create_job(job_id, uid)

    # FastAPI runs sync background functions in a thread pool executor automatically,
    # which is correct here since run_sync does blocking I/O (Gmail API, pikepdf).
    background_tasks.add_task(run_sync, uid, job_id)

    logger.info("sync_triggered", extra={"uid": uid, "job_id": job_id})
    return SyncResponse(job_id=job_id, message="Sync started. Poll /api/sync/status/{job_id} for progress.")


@router.get("/status/{job_id}", response_model=JobStatusResponse)
def get_sync_status(job_id: str, uid: str = Depends(get_current_uid)):
    """
    Poll the status of a sync job.
    The frontend calls this every 3 seconds after triggering a sync.
    """
    job = firestore_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Ensure users can only poll their own jobs
    if job.get("uid") != uid:
        raise HTTPException(status_code=403, detail="Forbidden")

    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        results=job.get("results"),
        error_reason=job.get("errorReason"),
    )
