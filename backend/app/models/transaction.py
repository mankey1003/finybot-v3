from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TransactionResponse(BaseModel):
    id: str
    card_provider: str
    statement_id: str
    date: datetime
    billing_month: str  # YYYY-MM
    description: str
    amount: float
    currency: str
    debit_or_credit: str
    category: str
    created_at: Optional[datetime] = None


class PaginatedTransactionsResponse(BaseModel):
    transactions: list[TransactionResponse]
    next_cursor: Optional[str] = None  # doc ID of last item; None means no more pages
    has_more: bool
