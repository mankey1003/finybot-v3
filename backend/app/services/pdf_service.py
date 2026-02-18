import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class WrongPasswordError(Exception):
    """Raised when pikepdf cannot open a PDF due to an incorrect password."""
    pass


class ScannedPdfError(Exception):
    """Raised when a PDF contains no extractable text (likely a scanned image)."""
    pass


def decrypt_pdf(pdf_bytes: bytes, password: str) -> bytes:
    """
    Decrypt a password-protected PDF using pikepdf.

    Returns decrypted PDF bytes.
    Raises WrongPasswordError if the password is incorrect.
    Raises any other exception for unexpected failures.
    """
    try:
        import pikepdf

        with pikepdf.open(io.BytesIO(pdf_bytes), password=password) as pdf:
            out = io.BytesIO()
            pdf.save(out)
            decrypted = out.getvalue()

        logger.info("pdf_decrypted", extra={"size_bytes": len(decrypted)})
        return decrypted

    except Exception as e:
        error_str = str(e).lower()
        error_type = type(e).__name__

        if "password" in error_str or "PasswordError" in error_type or "incorrect" in error_str:
            logger.warning("pdf_wrong_password", extra={"error": str(e)})
            raise WrongPasswordError(str(e))

        logger.error("pdf_decrypt_error", extra={"error": str(e), "type": error_type})
        raise


def extract_text_fallback(pdf_bytes: bytes) -> str:
    """
    Extract raw text from a PDF using pdfplumber.
    Used as a fallback check and for basic readability validation.
    """
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages_text = [page.extract_text() or "" for page in pdf.pages]

        text = "\n".join(pages_text)
        logger.info("pdf_text_extracted", extra={"char_count": len(text)})
        return text

    except Exception as e:
        logger.error("pdf_pdfplumber_failed", extra={"error": str(e)})
        return ""


def is_readable(pdf_bytes: bytes, min_chars: int = 100) -> bool:
    """
    Check if a PDF has enough extractable text to be processed.
    Returns False for scanned/image-only PDFs.
    """
    text = extract_text_fallback(pdf_bytes)
    readable = len(text.strip()) >= min_chars
    if not readable:
        logger.warning("pdf_not_readable", extra={"extracted_chars": len(text.strip())})
    return readable
