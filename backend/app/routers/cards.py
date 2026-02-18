import logging
import re

from fastapi import APIRouter, Depends, HTTPException

from app.middleware.auth_middleware import get_current_uid
from app.models.statement import AddCardProviderRequest, CardProviderResponse, UpdatePasswordRequest
from app.services import auth_service, firestore_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=list[CardProviderResponse])
def list_cards(uid: str = Depends(get_current_uid)):
    """Return all registered card providers for the authenticated user."""
    providers = firestore_service.get_card_providers(uid)
    return [
        CardProviderResponse(
            id=p["id"],
            name=p["name"],
            email_sender_pattern=p["emailSenderPattern"],
            subject_keyword=p["subjectKeyword"],
        )
        for p in providers
    ]


@router.post("", response_model=CardProviderResponse, status_code=201)
def add_card(body: AddCardProviderRequest, uid: str = Depends(get_current_uid)):
    """
    Register a new card provider.
    The PDF password is encrypted (Fernet) before storage — never stored in plaintext.
    """
    encrypted_password = auth_service.encrypt(body.password)

    provider_data = {
        "name": body.name,
        "emailSenderPattern": body.email_sender_pattern,
        "subjectKeyword": body.subject_keyword,
        "encryptedPassword": encrypted_password,
    }
    provider_id = firestore_service.add_card_provider(uid, provider_data)
    logger.info("card_provider_added", extra={"uid": uid, "provider_id": provider_id, "provider_name": body.name})

    return CardProviderResponse(
        id=provider_id,
        name=body.name,
        email_sender_pattern=body.email_sender_pattern,
        subject_keyword=body.subject_keyword,
    )


@router.put("/{provider_id}/password", status_code=204)
def update_password(
    provider_id: str,
    body: UpdatePasswordRequest,
    uid: str = Depends(get_current_uid),
):
    """
    Update the PDF statement password for a card provider.
    Called when a sync fails with 'wrong_password' error.
    """
    provider = firestore_service.get_card_provider(uid, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Card provider not found")

    encrypted_password = auth_service.encrypt(body.password)
    firestore_service.update_card_provider(uid, provider_id, {"encryptedPassword": encrypted_password})

    logger.info("card_password_updated", extra={"uid": uid, "provider_id": provider_id})


@router.delete("/{provider_id}", status_code=204)
def delete_card(provider_id: str, uid: str = Depends(get_current_uid)):
    """Remove a card provider. Does not delete associated statements or transactions."""
    provider = firestore_service.get_card_provider(uid, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Card provider not found")

    firestore_service.delete_card_provider(uid, provider_id)
    logger.info("card_provider_deleted", extra={"uid": uid, "provider_id": provider_id})
