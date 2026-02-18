from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class GeminiTransaction(BaseModel):
    date: str  # YYYY-MM-DD
    description: str
    amount: float
    debit_or_credit: str  # "debit" or "credit"
    category: str


class GeminiStatementOutput(BaseModel):
    statement_date: str  # YYYY-MM-DD
    billing_period_from: str  # YYYY-MM-DD
    billing_period_to: str  # YYYY-MM-DD
    due_date: str  # YYYY-MM-DD
    total_amount_due: float
    min_payment_due: float
    currency: str
    transactions: list[GeminiTransaction]


# ── Request / Response schemas for API ────────────────────────────────────────

class AddCardProviderRequest(BaseModel):
    name: str
    email_sender_pattern: str = Field(description="e.g. '@hdfcbank.com'")
    subject_keyword: str = Field(description="e.g. 'credit card statement'")
    password: str = Field(description="PDF statement password — stored encrypted")


class UpdatePasswordRequest(BaseModel):
    password: str


class CardProviderResponse(BaseModel):
    id: str
    name: str
    email_sender_pattern: str
    subject_keyword: str
    # password is never returned


class StatementResponse(BaseModel):
    id: str
    card_provider: str
    billing_month: str  # YYYY-MM
    statement_date: Optional[datetime]
    due_date: Optional[datetime]
    total_amount_due: float
    min_payment_due: float
    currency: str
    status: str
    error_reason: Optional[str] = None


class MonthlyReportResponse(BaseModel):
    billing_month: str
    statements: list[StatementResponse]
    total_across_cards: float
