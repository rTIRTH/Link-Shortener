"""One-time codes emailed to people (sign-up, and changing your email)."""
import hashlib
import hmac
import secrets
from datetime import timedelta

from .config import settings

CODE_LIFETIME = timedelta(minutes=10)
RESEND_AFTER_SECONDS = 60
MAX_CODE_ATTEMPTS = 5


def new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(*parts: str) -> str:
    """Only this fingerprint is stored, never the code. It is tied to who the code is for."""
    message = ":".join(parts).encode()
    return hmac.new(settings.secret_key.encode(), message, hashlib.sha256).hexdigest()


def codes_match(stored: str, given: str) -> bool:
    return hmac.compare_digest(stored, given)
