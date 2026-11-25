"""Password-reset links: signed, time-limited, and good for one use only.

Nothing is stored in the database. The link carries the user's id and a fingerprint of their
current password and email. Once the password (or the email) changes, the fingerprint no longer
matches, so a link cannot be used twice, and changing the password in Account also cancels any
link that is still out there.
"""
import hashlib
import hmac
import os

from itsdangerous import BadData, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from .config import settings
from .models import User

MAX_AGE_SECONDS = 3600  # a link works for one hour
_SALT = "password-reset"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt=_SALT)


def _fingerprint(user: User) -> str:
    message = f"{user.password_hash}:{user.email}".encode()
    return hmac.new(settings.secret_key.encode(), message, hashlib.sha256).hexdigest()[:20]


def make_token(user: User) -> str:
    return _serializer().dumps({"u": user.id, "f": _fingerprint(user)})


def user_for_token(db: Session, token: str) -> User | None:
    """The user this link belongs to, or None if it is forged, expired or already used."""
    try:
        data = _serializer().loads(token, max_age=MAX_AGE_SECONDS)
    except BadData:  # a bad signature, an expired link, or text that is not a link at all
        return None
    if not isinstance(data, dict) or not isinstance(data.get("u"), int):
        return None
    user = db.get(User, data["u"])
    if user is None or not hmac.compare_digest(str(data.get("f", "")), _fingerprint(user)):
        return None
    return user


def site_url(request) -> str:
    """The address to put in an emailed link.

    It comes from the server's own settings, never from the visitor's Host header: otherwise
    someone could ask for a reset with a made-up Host and get the victim emailed a link that
    leads to the attacker's site. Render tells every service its own address.
    """
    fixed = settings.base_url or os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    return fixed or str(request.base_url).rstrip("/")
