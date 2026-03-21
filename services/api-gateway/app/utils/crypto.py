"""Symmetric encryption for shared secrets at rest using Fernet (AES-128-CBC + HMAC)."""
import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken
import structlog

logger = structlog.get_logger()

from typing import Optional
_fernet: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    """Lazily initialise Fernet cipher from NeuraNAC_ENCRYPTION_KEY env var."""
    global _fernet
    if _fernet is not None:
        return _fernet

    raw_key = os.getenv("NeuraNAC_ENCRYPTION_KEY", "")
    if not raw_key:
        # Derive a deterministic key from API_SECRET_KEY for dev convenience.
        # In production, set NeuraNAC_ENCRYPTION_KEY to a proper Fernet key.
        fallback = os.getenv("API_SECRET_KEY", "dev_secret_key_change_in_production_min32")
        raw_key = base64.urlsafe_b64encode(hashlib.sha256(fallback.encode()).digest()).decode()
        logger.warning("NeuraNAC_ENCRYPTION_KEY not set — deriving from API_SECRET_KEY (not recommended for production)")

    _fernet = Fernet(raw_key)
    return _fernet


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a plaintext string and return a base64-encoded ciphertext."""
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted ciphertext back to plaintext."""
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.error("Failed to decrypt secret — key mismatch or corrupted ciphertext")
        return ""
