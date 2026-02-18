import logging
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.middleware.auth_middleware import get_current_uid
from app.services import firestore_service, gemini_service

logger = logging.getLogger(__name__)
router = APIRouter()


class InsightsResponse(BaseModel):
    months: list[str]
    spend_data: dict
    narrative: str


@router.get("", response_model=InsightsResponse)
def get_insights(
    uid: str = Depends(get_current_uid),
    months: str = Query(
        description="Comma-separated billing months to compare (YYYY-MM). E.g. '2026-01,2025-12,2025-11'"
    ),
):
    """
    Compare spending across months and return a Gemini-generated narrative explaining
    the differences.

    The frontend passes the months to compare (e.g. current month + 2 prior months).
    The response includes both the raw aggregated spend_data (for charts) and
    the AI-generated narrative explanation.
    """
    import re

    month_list = [m.strip() for m in months.split(",") if m.strip()]
    if not month_list:
        raise HTTPException(status_code=400, detail="At least one month is required")
    if len(month_list) > 6:
        raise HTTPException(status_code=400, detail="Maximum 6 months can be compared at once")

    invalid = [m for m in month_list if not re.match(r"^\d{4}-\d{2}$", m)]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid month format: {invalid}. Use YYYY-MM.")

    # Fetch all transactions for the requested months
    transactions = firestore_service.get_transactions_for_months(uid, month_list)
    if not transactions:
        raise HTTPException(status_code=404, detail="No transactions found for the requested months")

    # Fetch statement summaries for total-due amounts
    statements: dict[str, dict] = {}
    for month in month_list:
        for stmt in firestore_service.get_statements_for_month(uid, month):
            key = f"{stmt.get('cardProvider')}_{month}"
            statements[key] = stmt

    # Aggregate spend data per month
    spend_data: dict = {}
    for month in month_list:
        month_txs = [t for t in transactions if t.get("billingMonth") == month]

        by_category: dict[str, float] = defaultdict(float)
        by_card: dict[str, float] = defaultdict(float)
        total = 0.0

        for tx in month_txs:
            if tx.get("debitOrCredit") == "debit":
                amount = tx.get("amount", 0.0)
                total += amount
                by_category[tx.get("category", "Other")] += amount
                by_card[tx.get("cardProvider", "unknown")] += amount

        spend_data[month] = {
            "total": round(total, 2),
            "by_card": {k: round(v, 2) for k, v in by_card.items()},
            "by_category": {k: round(v, 2) for k, v in by_category.items()},
            "transaction_count": len(month_txs),
        }

    payload = {"months": month_list, "data": spend_data}

    logger.info("generating_insights", extra={"uid": uid, "months": month_list})
    narrative = gemini_service.generate_insights(payload)

    return InsightsResponse(
        months=month_list,
        spend_data=spend_data,
        narrative=narrative,
    )
