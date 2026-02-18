import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.middleware.auth_middleware import get_current_uid
from app.models.transaction import PaginatedTransactionsResponse, TransactionResponse
from app.services import firestore_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=PaginatedTransactionsResponse)
def list_transactions(
    uid: str = Depends(get_current_uid),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = Query(default=None, description="Document ID of the last item from the previous page"),
    billing_month: Optional[str] = Query(default=None, description="Filter by billing month (YYYY-MM)"),
    card_provider: Optional[str] = Query(default=None, description="Filter by card provider ID"),
):
    """
    Return paginated transactions ordered by date descending (newest first).

    Supports infinite scroll / lazy loading:
    - First call: omit cursor
    - Subsequent calls: pass cursor = next_cursor from the previous response
    - has_more=false means you've reached the end

    Note: Combining billing_month or card_provider filters with date ordering requires
    composite Firestore indexes. Add them to firestore.indexes.json before deploying.
    """
    tx_list, next_cursor = firestore_service.get_transactions(
        uid=uid,
        limit=limit,
        cursor_id=cursor,
        billing_month=billing_month,
        card_provider=card_provider,
    )

    transactions = []
    for tx in tx_list:
        try:
            transactions.append(
                TransactionResponse(
                    id=tx["id"],
                    card_provider=tx.get("cardProvider", ""),
                    statement_id=tx.get("statementId", ""),
                    date=tx["date"],
                    billing_month=tx.get("billingMonth", ""),
                    description=tx.get("description", ""),
                    amount=tx.get("amount", 0.0),
                    currency=tx.get("currency", ""),
                    debit_or_credit=tx.get("debitOrCredit", "debit"),
                    category=tx.get("category", "Other"),
                    created_at=tx.get("createdAt"),
                )
            )
        except Exception as e:
            logger.error(
                "transaction_serialization_error",
                extra={"tx_id": tx.get("id"), "error": str(e)},
            )

    return PaginatedTransactionsResponse(
        transactions=transactions,
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
    )
