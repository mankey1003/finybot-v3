import logging

from fastapi import APIRouter, Depends, HTTPException

from app.middleware.auth_middleware import get_current_uid
from app.models.statement import MonthlyReportResponse, StatementResponse
from app.services import firestore_service

logger = logging.getLogger(__name__)
router = APIRouter()


def _to_statement_response(s: dict) -> StatementResponse:
    return StatementResponse(
        id=s["id"],
        card_provider=s.get("cardProvider", ""),
        billing_month=s.get("billingMonth", ""),
        statement_date=s.get("statementDate"),
        due_date=s.get("dueDate"),
        total_amount_due=s.get("totalAmountDue", 0.0),
        min_payment_due=s.get("minPaymentDue", 0.0),
        currency=s.get("currency", ""),
        status=s.get("status", "unknown"),
        error_reason=s.get("errorReason"),
    )


@router.get("", response_model=list[StatementResponse])
def list_statements(uid: str = Depends(get_current_uid)):
    """
    Return all statement summaries for the user, ordered by billing month descending.
    Used to populate the monthly overview on the dashboard.
    """
    statements = firestore_service.get_statements(uid)
    return [_to_statement_response(s) for s in statements]


@router.get("/{billing_month}", response_model=MonthlyReportResponse)
def get_monthly_report(billing_month: str, uid: str = Depends(get_current_uid)):
    """
    Return the monthly bill report for a specific YYYY-MM across all cards.
    Includes per-card statement details and total spend across all cards.
    """
    # Validate format
    import re
    if not re.match(r"^\d{4}-\d{2}$", billing_month):
        raise HTTPException(status_code=400, detail="billing_month must be in YYYY-MM format")

    statements = firestore_service.get_statements_for_month(uid, billing_month)
    if not statements:
        raise HTTPException(status_code=404, detail=f"No statements found for {billing_month}")

    statement_responses = [_to_statement_response(s) for s in statements]

    # Total across all cards for this month (processed statements only)
    total = sum(
        s.get("totalAmountDue", 0.0)
        for s in statements
        if s.get("status") == "processed"
    )

    return MonthlyReportResponse(
        billing_month=billing_month,
        statements=statement_responses,
        total_across_cards=total,
    )
