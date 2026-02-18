import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from google_auth_oauthlib.flow import Flow
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import (
    FRONTEND_URL,
    GMAIL_SCOPES,
    GOOGLE_OAUTH_CLIENT_ID,
    GOOGLE_OAUTH_CLIENT_SECRET,
    OAUTH_REDIRECT_URI,
    STATE_SECRET_KEY,
)
from app.middleware.auth_middleware import get_current_uid
from app.services import auth_service, firestore_service

logger = logging.getLogger(__name__)
router = APIRouter()

_state_serializer = URLSafeTimedSerializer(STATE_SECRET_KEY)
_STATE_SALT = "gmail-oauth-state"
_STATE_MAX_AGE = 600  # 10 minutes


def _build_flow() -> Flow:
    return Flow.from_client_config(
        client_config={
            "web": {
                "client_id": GOOGLE_OAUTH_CLIENT_ID,
                "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [OAUTH_REDIRECT_URI],
            }
        },
        scopes=GMAIL_SCOPES,
        redirect_uri=OAUTH_REDIRECT_URI,
    )


@router.get("/gmail/initiate")
def initiate_gmail_oauth(uid: str = Depends(get_current_uid)):
    """
    Flow 2 — Step 1: Generate the Google consent URL.
    Called by the frontend with a Firebase ID token.
    Returns { auth_url } which the frontend then navigates to.

    access_type="offline" + prompt="consent" ensures Google returns a refresh_token
    suitable for background Gmail access without user interaction.
    """
    flow = _build_flow()

    # Sign the uid into the state parameter to recover it in the callback
    state = _state_serializer.dumps(uid, salt=_STATE_SALT)

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",      # force refresh_token issuance even on repeat auth
        state=state,
        include_granted_scopes="true",
    )

    logger.info("gmail_oauth_initiated", extra={"uid": uid})
    return JSONResponse({"auth_url": auth_url})


@router.get("/gmail/callback")
def gmail_oauth_callback(code: str, state: str, request: Request):
    """
    Flow 2 — Step 2: Handle Google's redirect back after user consent.
    Called by Google's OAuth server — no Firebase ID token here.
    The signed state encodes the uid for CSRF protection.

    On success: encrypts the refresh token, stores it in Firestore,
    and redirects the user back to the frontend dashboard.
    """
    # Verify state (CSRF protection + uid recovery)
    try:
        uid = _state_serializer.loads(state, salt=_STATE_SALT, max_age=_STATE_MAX_AGE)
    except SignatureExpired:
        logger.warning("gmail_oauth_state_expired", extra={"state": state[:20]})
        return RedirectResponse(f"{FRONTEND_URL}/connect-gmail?error=session_expired")
    except BadSignature:
        logger.warning("gmail_oauth_state_invalid", extra={"state": state[:20]})
        return RedirectResponse(f"{FRONTEND_URL}/connect-gmail?error=invalid_state")

    # Exchange authorization code for tokens
    try:
        flow = _build_flow()
        flow.fetch_token(code=code)
        credentials = flow.credentials
    except Exception as e:
        logger.error("gmail_oauth_token_exchange_failed", extra={"uid": uid, "error": str(e)})
        return RedirectResponse(f"{FRONTEND_URL}/connect-gmail?error=token_exchange_failed")

    refresh_token = credentials.refresh_token
    if not refresh_token:
        # This happens if the user previously authorized and prompt=consent was not set,
        # or if the account already has a valid token. Should not happen with prompt=consent.
        logger.error("gmail_oauth_no_refresh_token", extra={"uid": uid})
        return RedirectResponse(f"{FRONTEND_URL}/connect-gmail?error=no_refresh_token")

    # Encrypt and store the refresh token
    try:
        encrypted = auth_service.encrypt(refresh_token)
        firestore_service.set_gmail_connected(uid, encrypted)
    except Exception as e:
        logger.error("gmail_refresh_token_store_failed", extra={"uid": uid, "error": str(e)})
        return RedirectResponse(f"{FRONTEND_URL}/connect-gmail?error=storage_failed")

    logger.info("gmail_oauth_complete", extra={"uid": uid})
    return RedirectResponse(f"{FRONTEND_URL}/dashboard?gmail_connected=1")


@router.get("/status")
def get_auth_status(uid: str = Depends(get_current_uid)):
    """
    Returns whether the user has completed Gmail OAuth (Flow 2).
    The frontend checks this on login to decide which screen to show.
    """
    user = firestore_service.get_user(uid)
    gmail_connected = user.get("gmailConnected", False) if user else False
    return {"uid": uid, "gmail_connected": gmail_connected}
