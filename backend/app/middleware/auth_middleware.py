import logging
from fastapi import Header, HTTPException, Depends
from app.services.auth_service import verify_firebase_token

logger = logging.getLogger(__name__)


def get_current_uid(authorization: str = Header(...)) -> str:
    """
    FastAPI dependency that extracts and verifies the Firebase ID token.
    Attach with: uid: str = Depends(get_current_uid)

    The frontend must send: Authorization: Bearer <firebase_id_token>
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header must be 'Bearer <token>'")

    token = authorization[len("Bearer "):]
    uid = verify_firebase_token(token)

    if not uid:
        raise HTTPException(status_code=401, detail="Invalid or expired Firebase ID token")

    return uid
