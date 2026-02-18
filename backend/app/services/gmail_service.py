import base64
import logging
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, GMAIL_SCOPES

logger = logging.getLogger(__name__)


def _build_service(refresh_token: str):
    """Build an authenticated Gmail API service client from a stored refresh token."""
    logger.info("gmail_building_service", extra={"refresh_token_prefix": refresh_token[:8] + "..."})
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_OAUTH_CLIENT_ID,
        client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
        scopes=GMAIL_SCOPES,
    )
    try:
        creds.refresh(Request())
        logger.info("gmail_token_refreshed_ok")
    except Exception as e:
        logger.error("gmail_token_refresh_failed", extra={"error": str(e)})
        raise
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def search_messages(refresh_token: str, query: str) -> list[dict]:
    """
    Search Gmail for messages matching the query.
    Returns a list of {id, threadId} dicts.
    Paginates automatically until all results are fetched.
    """
    service = _build_service(refresh_token)
    messages: list[dict] = []
    next_page_token: Optional[str] = None

    while True:
        try:
            params = {"userId": "me", "q": query, "maxResults": 50}
            if next_page_token:
                params["pageToken"] = next_page_token

            result = service.users().messages().list(**params).execute()
        except Exception as e:
            logger.error("gmail_search_failed", extra={"query": query, "error": str(e)})
            break

        messages.extend(result.get("messages", []))
        next_page_token = result.get("nextPageToken")
        if not next_page_token:
            break

    if messages:
        logger.info("gmail_search_complete", extra={"query": query, "count": len(messages)})
    else:
        logger.warning(
            "gmail_search_no_results",
            extra={"query": query, "hint": "No emails matched — verify sender pattern and subject keyword"},
        )
    return messages


def get_pdf_attachment(
    refresh_token: str, message_id: str
) -> Optional[tuple[str, bytes]]:
    """
    Download the first PDF attachment from a Gmail message.
    Returns (filename, pdf_bytes) or None if no PDF attachment found.
    """
    service = _build_service(refresh_token)

    try:
        msg = service.users().messages().get(
            userId="me", id=message_id, format="full"
        ).execute()
    except Exception as e:
        logger.error(
            "gmail_get_message_failed",
            extra={"message_id": message_id, "error": str(e)},
        )
        return None

    payload = msg.get("payload", {})
    parts = _flatten_parts(payload.get("parts", []))

    # Also include the top-level payload itself in case it's a single-part message
    all_parts = [payload] + parts

    logger.info(
        "gmail_message_parts",
        extra={
            "message_id": message_id,
            "payload_mime_type": payload.get("mimeType"),
            "parts_count": len(parts),
            "parts_summary": [
                {"filename": p.get("filename", ""), "mimeType": p.get("mimeType", ""), "hasBody": bool(p.get("body"))}
                for p in all_parts
            ],
        },
    )

    for part in all_parts:
        filename = part.get("filename", "")
        if not filename.lower().endswith(".pdf"):
            continue

        body = part.get("body", {})

        # Small inline attachment (data directly in body)
        if "data" in body:
            pdf_bytes = base64.urlsafe_b64decode(body["data"])
            logger.info("gmail_attachment_inline", extra={"message_id": message_id, "attachment_filename": filename})
            return filename, pdf_bytes

        # Large attachment referenced by ID
        att_id = body.get("attachmentId")
        if not att_id:
            continue

        try:
            att = service.users().messages().attachments().get(
                userId="me", messageId=message_id, id=att_id
            ).execute()
            pdf_bytes = base64.urlsafe_b64decode(att["data"])
            logger.info(
                "gmail_attachment_downloaded",
                extra={"message_id": message_id, "attachment_filename": filename, "size": len(pdf_bytes)},
            )
            return filename, pdf_bytes
        except Exception as e:
            logger.error(
                "gmail_attachment_download_failed",
                extra={"message_id": message_id, "attachment_id": att_id, "error": str(e)},
            )

    logger.warning("gmail_no_pdf_found", extra={"message_id": message_id})
    return None


def _flatten_parts(parts: list) -> list:
    """Recursively flatten MIME multipart tree into a flat list of parts."""
    flat = []
    for part in parts:
        flat.append(part)
        flat.extend(_flatten_parts(part.get("parts", [])))
    return flat
