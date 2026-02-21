import logging
from datetime import datetime, timezone
from typing import Any, Optional

from google.cloud import firestore

logger = logging.getLogger(__name__)

_db = firestore.Client()

_PAGE_SIZE_MAX = 100


# ── Helpers ────────────────────────────────────────────────────────────────────

def _users(uid: str):
    return _db.collection("users").document(uid)

def _cards(uid: str):
    return _users(uid).collection("card_providers")

def _statements(uid: str):
    return _users(uid).collection("statements")

def _transactions(uid: str):
    return _users(uid).collection("transactions")

def _chats(uid: str):
    return _users(uid).collection("chats")

def _messages(uid: str, chat_id: str):
    return _chats(uid).document(chat_id).collection("messages")

def _jobs():
    return _db.collection("jobs")

def _doc_to_dict(doc) -> Optional[dict]:
    if not doc.exists:
        return None
    return {"id": doc.id, **doc.to_dict()}


# ── User ───────────────────────────────────────────────────────────────────────

def get_user(uid: str) -> Optional[dict]:
    return _doc_to_dict(_users(uid).get())


def upsert_user(uid: str, data: dict) -> None:
    _users(uid).set(data, merge=True)


def set_gmail_connected(uid: str, encrypted_refresh_token: str) -> None:
    _users(uid).set(
        {
            "gmailConnected": True,
            "gmailRefreshToken": encrypted_refresh_token,
            "gmailConnectedAt": datetime.now(timezone.utc),
        },
        merge=True,
    )


def get_gmail_refresh_token(uid: str) -> Optional[str]:
    user = get_user(uid)
    if not user:
        return None
    return user.get("gmailRefreshToken")


# ── Card Providers ─────────────────────────────────────────────────────────────

def get_card_providers(uid: str) -> list[dict]:
    docs = _cards(uid).order_by("addedAt").get()
    providers = [_doc_to_dict(d) for d in docs]
    logger.info(
        "card_providers_loaded",
        extra={
            "uid": uid,
            "count": len(providers),
            "providers": [{"id": p["id"], "name": p.get("name")} for p in providers],
        },
    )
    return providers


def get_card_provider(uid: str, provider_id: str) -> Optional[dict]:
    return _doc_to_dict(_cards(uid).document(provider_id).get())


def add_card_provider(uid: str, data: dict) -> str:
    """Add a new card provider and return the generated document ID."""
    ref = _cards(uid).document()
    ref.set({**data, "addedAt": datetime.now(timezone.utc)})
    return ref.id


def update_card_provider(uid: str, provider_id: str, data: dict) -> None:
    _cards(uid).document(provider_id).set(data, merge=True)


def delete_card_provider(uid: str, provider_id: str) -> None:
    _cards(uid).document(provider_id).delete()


# ── Statements ─────────────────────────────────────────────────────────────────

def get_statement(uid: str, statement_id: str) -> Optional[dict]:
    return _doc_to_dict(_statements(uid).document(statement_id).get())


def statement_exists_by_gmail_id(uid: str, gmail_message_id: str) -> bool:
    """Check if a statement has already been processed for a given Gmail message ID."""
    docs = (
        _statements(uid)
        .where("gmailMessageId", "==", gmail_message_id)
        .where("status", "==", "processed")
        .limit(1)
        .get()
    )
    exists = len(list(docs)) > 0
    logger.info(
        "idempotency_check",
        extra={"uid": uid, "gmail_message_id": gmail_message_id, "already_processed": exists},
    )
    return exists


def upsert_statement(uid: str, statement_id: str, data: dict) -> None:
    _statements(uid).document(statement_id).set(data, merge=True)


def delete_statement(uid: str, statement_id: str) -> None:
    _statements(uid).document(statement_id).delete()


def get_statements(uid: str) -> list[dict]:
    """Return all statements for a user ordered by billing month descending."""
    docs = _statements(uid).order_by("billingMonth", direction=firestore.Query.DESCENDING).get()
    return [_doc_to_dict(d) for d in docs]


def get_statements_for_month(uid: str, billing_month: str) -> list[dict]:
    docs = (
        _statements(uid)
        .where("billingMonth", "==", billing_month)
        .get()
    )
    return [_doc_to_dict(d) for d in docs]


# ── Transactions ───────────────────────────────────────────────────────────────

def batch_add_transactions(uid: str, tx_list: list[dict]) -> None:
    """
    Write transactions in Firestore batches of 500 (Firestore limit).
    Each transaction gets an auto-generated document ID.
    """
    chunk_size = 500
    for i in range(0, len(tx_list), chunk_size):
        batch = _db.batch()
        for tx in tx_list[i : i + chunk_size]:
            ref = _transactions(uid).document()
            batch.set(ref, tx)
        batch.commit()

    logger.info("transactions_written", extra={"uid": uid, "count": len(tx_list)})


def get_transactions(
    uid: str,
    limit: int = 20,
    cursor_id: Optional[str] = None,
    billing_month: Optional[str] = None,
    card_provider: Optional[str] = None,
) -> tuple[list[dict], Optional[str]]:
    """
    Paginate transactions ordered by date descending.

    Args:
        cursor_id: document ID of the last item from the previous page.
                   Pass None for the first page.
    Returns:
        (list of transaction dicts, next_cursor_id or None)

    Note: Firestore requires composite indexes for compound queries.
    Required indexes (add to firestore.indexes.json):
    - Collection: transactions, Fields: billingMonth ASC, date DESC
    - Collection: transactions, Fields: cardProvider ASC, date DESC
    """
    limit = min(limit, _PAGE_SIZE_MAX)
    col = _transactions(uid)

    query = col.order_by("date", direction=firestore.Query.DESCENDING)

    if billing_month:
        query = col.order_by("billingMonth").order_by(
            "date", direction=firestore.Query.DESCENDING
        ).where("billingMonth", "==", billing_month)

    if card_provider:
        query = col.order_by("cardProvider").order_by(
            "date", direction=firestore.Query.DESCENDING
        ).where("cardProvider", "==", card_provider)

    if cursor_id:
        cursor_doc = col.document(cursor_id).get()
        if cursor_doc.exists:
            query = query.start_after(cursor_doc)
        else:
            logger.warning("pagination_cursor_not_found", extra={"cursor_id": cursor_id})

    docs = list(query.limit(limit + 1).get())  # fetch one extra to detect next page

    has_more = len(docs) > limit
    if has_more:
        docs = docs[:limit]

    results = [_doc_to_dict(d) for d in docs]
    next_cursor = docs[-1].id if has_more else None

    return results, next_cursor


def get_transactions_for_months(uid: str, billing_months: list[str]) -> list[dict]:
    """Fetch all transactions for a set of billing months (for insights aggregation)."""
    results = []
    for month in billing_months:
        docs = (
            _transactions(uid)
            .where("billingMonth", "==", month)
            .get()
        )
        results.extend([_doc_to_dict(d) for d in docs])
    return results


# ── Jobs ───────────────────────────────────────────────────────────────────────

def create_job(job_id: str, uid: str) -> None:
    _jobs().document(job_id).set(
        {
            "uid": uid,
            "status": "pending",
            "triggeredAt": datetime.now(timezone.utc),
            "completedAt": None,
            "results": None,
            "errorReason": None,
        }
    )


def update_job(job_id: str, data: dict) -> None:
    _jobs().document(job_id).set(data, merge=True)


def get_job(job_id: str) -> Optional[dict]:
    return _doc_to_dict(_jobs().document(job_id).get())


# ── Chats ──────────────────────────────────────────────────────────────────────

def create_chat(uid: str, chat_id: str, title: str) -> dict:
    now = datetime.now(timezone.utc)
    data = {"title": title, "createdAt": now, "updatedAt": now}
    _chats(uid).document(chat_id).set(data)
    return {"id": chat_id, **data}


def get_chats(uid: str) -> list[dict]:
    docs = _chats(uid).order_by("updatedAt", direction=firestore.Query.DESCENDING).get()
    return [_doc_to_dict(d) for d in docs]


def get_chat(uid: str, chat_id: str) -> Optional[dict]:
    return _doc_to_dict(_chats(uid).document(chat_id).get())


def delete_chat(uid: str, chat_id: str) -> None:
    # Delete all messages in subcollection first
    msgs = _messages(uid, chat_id).get()
    for msg in msgs:
        msg.reference.delete()
    _chats(uid).document(chat_id).delete()


def update_chat_title(uid: str, chat_id: str, title: str) -> None:
    _chats(uid).document(chat_id).set(
        {"title": title, "updatedAt": datetime.now(timezone.utc)}, merge=True
    )


def touch_chat(uid: str, chat_id: str) -> None:
    _chats(uid).document(chat_id).set(
        {"updatedAt": datetime.now(timezone.utc)}, merge=True
    )


def add_message(uid: str, chat_id: str, message_dict: dict) -> str:
    ref = _messages(uid, chat_id).document()
    ref.set({**message_dict, "createdAt": datetime.now(timezone.utc)})
    return ref.id


def get_messages(uid: str, chat_id: str) -> list[dict]:
    docs = _messages(uid, chat_id).order_by("createdAt").get()
    return [_doc_to_dict(d) for d in docs]
