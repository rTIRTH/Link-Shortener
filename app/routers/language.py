from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..i18n import LANGUAGES
from ..models import User

router = APIRouter()


def safe_next(value: str) -> str:
    """Only allow a path on this site, so the form can't be used to send people elsewhere."""
    value = (value or "/").strip()
    if not value.startswith("/") or value.startswith("//") or "\\" in value or "\n" in value:
        return "/"
    return value


def set_language_cookie(response, lang: str) -> None:
    response.set_cookie("lang", lang, max_age=365 * 24 * 3600, httponly=True,
                        samesite="lax", secure=settings.https_only)


@router.post("/language")
def change_language(
    request: Request,
    lang: str = Form(...),
    next_url: str = Form("/", alias="next"),
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    response = RedirectResponse(safe_next(next_url), status_code=303)
    if lang in LANGUAGES:
        if user:  # remember it on the account, so it follows the person to other devices
            user.language = lang
            db.commit()
        set_language_cookie(response, lang)
    return response
