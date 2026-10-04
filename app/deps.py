from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User


class NotAuthenticated(Exception):
    """Raised when a page needs login. main.py turns it into a redirect."""


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    return db.get(User, user_id) if user_id else None


def require_user(user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        raise NotAuthenticated()
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    # 404 (not 403) so strangers can't even tell the page exists
    if user.username not in settings.admin_usernames:
        raise HTTPException(404, "Page not found.")
    return user


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
