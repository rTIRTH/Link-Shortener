from fastapi import Depends, Request
from sqlalchemy.orm import Session

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


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
