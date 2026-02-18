import logging
from datetime import datetime, timezone
from typing import Optional

from app.services import auth_service, firestore_service, gemini_service, gmail_service, pdf_service
from app.services.pdf_service import WrongPasswordError

logger = logging.getLogger(__name__)


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse a YYYY-MM-DD string into a timezone-aware datetime, or return None."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        logger.warning("invalid_date_string", extra={"value": date_str})
        return None


def run_sync(uid: str, job_id: str) -> None:
    """
    Full Gmail → PDF → Gemini → Firestore pipeline.
    Designed to run in a background thread (FastAPI BackgroundTasks).
    Updates the job document in Firestore throughout for frontend polling.
    """
    logger.info("sync_started", extra={"uid": uid, "job_id": job_id})
    firestore_service.update_job(job_id, {"status": "processing"})

    try:
        # ── 1. Load user and decrypt Gmail refresh token ──────────────────────
        user = firestore_service.get_user(uid)
        if not user or not user.get("gmailConnected"):
            _fail_job(job_id, "gmail_not_connected")
            return

        encrypted_token = user.get("gmailRefreshToken")
        if not encrypted_token:
            _fail_job(job_id, "no_refresh_token")
            return

        try:
            refresh_token = auth_service.decrypt(encrypted_token)
        except Exception as e:
            logger.error("refresh_token_decrypt_failed", extra={"uid": uid, "error": str(e)})
            _fail_job(job_id, "refresh_token_decrypt_failed")
            return

        # ── 2. Load card providers ────────────────────────────────────────────
        card_providers = firestore_service.get_card_providers(uid)
        if not card_providers:
            _fail_job(job_id, "no_cards_configured")
            return

        results: dict = {"processed": 0, "skipped": 0, "failed": 0, "errors": []}

        for provider in card_providers:
            _process_provider(uid, provider, refresh_token, results)

        # ── 3. Mark job complete ──────────────────────────────────────────────
        firestore_service.update_job(
            job_id,
            {
                "status": "done",
                "completedAt": datetime.now(timezone.utc),
                "results": results,
            },
        )
        # Update user's lastSyncAt
        firestore_service.upsert_user(uid, {"lastSyncAt": datetime.now(timezone.utc)})
        logger.info("sync_completed", extra={"uid": uid, "job_id": job_id, "results": results})

    except Exception as e:
        logger.error("sync_unexpected_error", extra={"uid": uid, "job_id": job_id, "error": str(e)})
        _fail_job(job_id, str(e)[:500])


def _process_provider(uid: str, provider: dict, refresh_token: str, results: dict) -> None:
    """Process all unprocessed PDF statements for one card provider."""
    provider_id = provider["id"]
    provider_name = provider.get("name", provider_id)
    encrypted_password = provider.get("encryptedPassword", "")

    logger.info(
        "provider_sync_start",
        extra={
            "uid": uid,
            "provider_id": provider_id,
            "provider_name": provider_name,
            "has_password": bool(encrypted_password),
            "email_sender_pattern": provider.get("emailSenderPattern", "<not set>"),
            "subject_keyword": provider.get("subjectKeyword", "<not set>"),
        },
    )

    pdf_password = ""
    if encrypted_password:
        try:
            pdf_password = auth_service.decrypt(encrypted_password)
            logger.info("pdf_password_decrypted", extra={"provider_id": provider_id})
        except Exception as e:
            logger.error(
                "pdf_password_decrypt_failed",
                extra={"uid": uid, "provider_id": provider_id, "error": str(e)},
            )

    # Build Gmail search query from provider config
    query_parts = ["has:attachment", "filename:pdf"]
    if provider.get("emailSenderPattern"):
        sender = provider["emailSenderPattern"]
        if sender.startswith("@"):
            sender = f"*{sender}"  # "@hdfcbank.com" → "*@hdfcbank.com"
        query_parts.append(f"from:{sender}")
    else:
        logger.warning(
            "provider_missing_email_pattern",
            extra={"provider_id": provider_id, "note": "query will match ALL senders with PDF attachments"},
        )
    if provider.get("subjectKeyword"):
        query_parts.append(f"subject:\"{provider['subjectKeyword']}\"")
    else:
        logger.warning(
            "provider_missing_subject_keyword",
            extra={"provider_id": provider_id, "note": "query will match any subject with PDF attachments"},
        )
    query = " ".join(query_parts)

    logger.info("gmail_query_built", extra={"provider_id": provider_id, "query": query})

    messages = gmail_service.search_messages(refresh_token, query)
    if not messages:
        logger.warning(
            "no_messages_found",
            extra={
                "provider_id": provider_id,
                "provider_name": provider_name,
                "query": query,
                "hint": "Check emailSenderPattern and subjectKeyword match actual emails in Gmail",
            },
        )
        return

    logger.info(
        "messages_found",
        extra={"provider_id": provider_id, "provider_name": provider_name, "count": len(messages)},
    )

    provider_results: dict = {"processed": 0, "skipped": 0, "failed": 0}
    for msg in messages:
        msg_id = msg["id"]
        _process_message(uid, provider_id, msg_id, pdf_password, refresh_token, results)
        # Track per-provider breakdown for the final log
        provider_results["processed"] = results["processed"]
        provider_results["skipped"] = results["skipped"]
        provider_results["failed"] = results["failed"]

    logger.info(
        "provider_sync_done",
        extra={
            "provider_id": provider_id,
            "provider_name": provider_name,
            "messages_found": len(messages),
            "processed": results["processed"],
            "skipped": results["skipped"],
            "failed": results["failed"],
        },
    )


def _process_message(
    uid: str,
    provider_id: str,
    msg_id: str,
    pdf_password: str,
    refresh_token: str,
    results: dict,
) -> None:
    """Download, decrypt, extract, and store one Gmail message's PDF statement."""

    logger.info(
        "message_processing_start",
        extra={"uid": uid, "provider_id": provider_id, "msg_id": msg_id},
    )

    # Idempotency: skip already-processed messages
    already_exists = firestore_service.statement_exists_by_gmail_id(uid, msg_id)
    if already_exists:
        logger.info(
            "statement_already_processed",
            extra={"uid": uid, "provider_id": provider_id, "msg_id": msg_id},
        )
        results["skipped"] += 1
        return

    logger.info(
        "message_not_yet_processed",
        extra={"uid": uid, "provider_id": provider_id, "msg_id": msg_id},
    )

    # Provisional statement doc so failures are visible to the user
    temp_id = f"{provider_id}_processing_{msg_id[:8]}"
    firestore_service.upsert_statement(
        uid,
        temp_id,
        {
            "cardProvider": provider_id,
            "gmailMessageId": msg_id,
            "status": "processing",
            "processedAt": None,
        },
    )

    try:
        # ── Download PDF ──────────────────────────────────────────────────────
        logger.info("downloading_pdf_attachment", extra={"uid": uid, "provider_id": provider_id, "msg_id": msg_id})
        attachment = gmail_service.get_pdf_attachment(refresh_token, msg_id)
        if not attachment:
            raise ValueError("No PDF attachment found in email")
        filename, pdf_bytes = attachment
        logger.info(
            "pdf_attachment_downloaded",
            extra={"uid": uid, "provider_id": provider_id, "msg_id": msg_id, "attachment_filename": filename, "size_bytes": len(pdf_bytes)},
        )

        # ── Decrypt PDF ───────────────────────────────────────────────────────
        if pdf_password:
            logger.info("decrypting_pdf", extra={"uid": uid, "provider_id": provider_id, "msg_id": msg_id})
            try:
                pdf_bytes = pdf_service.decrypt_pdf(pdf_bytes, pdf_password)
            except WrongPasswordError:
                logger.error(
                    "pdf_wrong_password",
                    extra={"uid": uid, "provider_id": provider_id, "msg_id": msg_id,
                           "hint": "Update PDF password via PUT /api/cards/{id}/password"},
                )
                firestore_service.upsert_statement(
                    uid, temp_id, {"status": "failed", "errorReason": "wrong_password"}
                )
                results["failed"] += 1
                results["errors"].append(f"{provider_id}: wrong PDF password — update it in card settings")
                return
        else:
            logger.info("pdf_no_password_set", extra={"uid": uid, "provider_id": provider_id, "msg_id": msg_id})

        # ── Readability check ─────────────────────────────────────────────────
        logger.info("checking_pdf_readability", extra={"uid": uid, "provider_id": provider_id, "msg_id": msg_id})
        if not pdf_service.is_readable(pdf_bytes):
            logger.error(
                "pdf_not_readable_scanned",
                extra={"uid": uid, "provider_id": provider_id, "msg_id": msg_id},
            )
            firestore_service.upsert_statement(
                uid, temp_id, {"status": "failed", "errorReason": "scanned_pdf_unsupported"}
            )
            results["failed"] += 1
            results["errors"].append(f"{provider_id}/{msg_id[:8]}: scanned PDF — OCR not yet supported")
            return

        logger.info("pdf_is_readable", extra={"uid": uid, "provider_id": provider_id, "msg_id": msg_id})

        # ── Gemini extraction ─────────────────────────────────────────────────
        logger.info("sending_pdf_to_gemini", extra={"uid": uid, "provider_id": provider_id, "msg_id": msg_id})
        extracted = gemini_service.extract_statement(pdf_bytes)
        if not extracted:
            logger.error(
                "gemini_returned_none",
                extra={"uid": uid, "provider_id": provider_id, "msg_id": msg_id},
            )
            firestore_service.upsert_statement(
                uid, temp_id, {"status": "failed", "errorReason": "gemini_extraction_failed"}
            )
            results["failed"] += 1
            results["errors"].append(f"{provider_id}/{msg_id[:8]}: Gemini extraction failed")
            return

        logger.info(
            "gemini_extraction_done",
            extra={
                "uid": uid,
                "provider_id": provider_id,
                "msg_id": msg_id,
                "billing_period_from": extracted.billing_period_from,
                "billing_period_to": extracted.billing_period_to,
                "total_amount_due": extracted.total_amount_due,
                "tx_count": len(extracted.transactions),
            },
        )

        # ── Derive billing month and final statement ID ───────────────────────
        if not extracted.billing_period_to:
            logger.error(
                "gemini_missing_billing_period_to",
                extra={"uid": uid, "provider_id": provider_id, "msg_id": msg_id},
            )
            firestore_service.upsert_statement(
                uid, temp_id, {"status": "failed", "errorReason": "missing_billing_period_to"}
            )
            results["failed"] += 1
            results["errors"].append(f"{provider_id}/{msg_id[:8]}: Gemini did not return billing_period_to")
            return

        billing_month = extracted.billing_period_to[:7]  # YYYY-MM
        final_id = f"{provider_id}_{billing_month}"
        logger.info(
            "billing_month_derived",
            extra={"uid": uid, "provider_id": provider_id, "msg_id": msg_id, "billing_month": billing_month, "final_id": final_id},
        )

        # Skip if this billing month is already fully processed
        existing = firestore_service.get_statement(uid, final_id)
        if existing and existing.get("status") == "processed":
            logger.info(
                "billing_month_already_processed",
                extra={"uid": uid, "provider_id": provider_id, "billing_month": billing_month, "final_id": final_id},
            )
            firestore_service.delete_statement(uid, temp_id)
            results["skipped"] += 1
            return

        # ── Validate extracted total vs statement total ────────────────────────
        debit_sum = sum(t.amount for t in extracted.transactions if t.debit_or_credit == "debit")
        if extracted.total_amount_due and abs(debit_sum - extracted.total_amount_due) > 50:
            logger.warning(
                "amount_mismatch",
                extra={
                    "uid": uid,
                    "statement_id": final_id,
                    "sum_of_debits": debit_sum,
                    "stated_total": extracted.total_amount_due,
                },
            )

        # ── Write statement ───────────────────────────────────────────────────
        stmt_data = {
            "cardProvider": provider_id,
            "billingMonth": billing_month,
            "statementDate": _parse_date(extracted.statement_date),
            "dueDate": _parse_date(extracted.due_date),
            "billingPeriodFrom": _parse_date(extracted.billing_period_from),
            "billingPeriodTo": _parse_date(extracted.billing_period_to),
            "totalAmountDue": extracted.total_amount_due,
            "minPaymentDue": extracted.min_payment_due,
            "currency": extracted.currency,
            "gmailMessageId": msg_id,
            "status": "processed",
            "processedAt": datetime.now(timezone.utc),
            "errorReason": None,
        }
        firestore_service.upsert_statement(uid, final_id, stmt_data)
        firestore_service.delete_statement(uid, temp_id)

        # ── Batch write transactions ──────────────────────────────────────────
        tx_docs = [
            {
                "cardProvider": provider_id,
                "statementId": final_id,
                "date": _parse_date(tx.date),
                "billingMonth": billing_month,
                "description": tx.description,
                "amount": tx.amount,
                "currency": extracted.currency,
                "debitOrCredit": tx.debit_or_credit,
                "category": tx.category,
                "createdAt": datetime.now(timezone.utc),
            }
            for tx in extracted.transactions
        ]
        firestore_service.batch_add_transactions(uid, tx_docs)

        results["processed"] += 1
        logger.info(
            "statement_processed",
            extra={
                "uid": uid,
                "provider_id": provider_id,
                "billing_month": billing_month,
                "tx_count": len(tx_docs),
            },
        )

    except Exception as e:
        logger.error(
            "message_processing_failed",
            extra={"uid": uid, "provider_id": provider_id, "msg_id": msg_id, "error": str(e)},
        )
        firestore_service.upsert_statement(
            uid,
            temp_id,
            {"status": "failed", "errorReason": str(e)[:200]},
        )
        results["failed"] += 1
        results["errors"].append(f"{provider_id}/{msg_id[:8]}: {str(e)[:100]}")


def _fail_job(job_id: str, reason: str) -> None:
    firestore_service.update_job(
        job_id,
        {
            "status": "failed",
            "completedAt": datetime.now(timezone.utc),
            "errorReason": reason,
        },
    )
    logger.error("sync_job_failed", extra={"job_id": job_id, "reason": reason})
