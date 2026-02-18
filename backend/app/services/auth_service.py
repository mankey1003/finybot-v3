import logging
from typing import Optional

import firebase_admin
from firebase_admin import auth, credentials

from app.config import fernet

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK once.
# On Cloud Run, Application Default Credentials are used automatically.
# For local dev, falls back to service-account.json if present.
import os as _os
try:
    firebase_admin.get_app()
except ValueError:
    _sa_path = _os.path.join(_os.path.dirname(__file__), "..", "..", "service-account.json")
    if _os.path.exists(_sa_path):
        firebase_admin.initialize_app(credentials.Certificate(_os.path.abspath(_sa_path)))
    else:
        firebase_admin.initialize_app()


def verify_firebase_token(id_token: str) -> Optional[str]:
    """Verify a Firebase ID token and return the user's UID, or None on failure."""
    try:
        decoded = auth.verify_id_token(id_token)
        return decoded["uid"]
    except Exception as e:
        logger.error("firebase_token_verification_failed", extra={"error": str(e)})
        return None


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string using Fernet symmetric encryption.

    POC: uses a single app-level key stored in FERNET_KEY env var.
    TECH DEBT: Replace with Cloud KMS envelope encryption before production.
    See CLAUDE.md → Technical Debt Register #1.
    """
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted string."""
    return fernet.decrypt(ciphertext.encode()).decode()
