from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..profile import THEMES
from .language import safe_next

router = APIRouter()


@router.post("/mode")
def change_mode(
    request: Request,
    theme: str = Form(...),
    next_url: str = Form("/", alias="next"),
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The light / system default / dark switch in the top bar. Open to visitors too.

    The page's script sends this in the background (Accept: application/json). Without
    JavaScript the buttons are an ordinary form and the person is sent back where they were.
    """
    if theme not in THEMES:
        raise HTTPException(400, "Unknown theme.")
    if user:  # remember it on the account, so it follows the person to other devices
        user.theme = theme
        db.commit()
    if "application/json" in request.headers.get("accept", ""):
        response = JSONResponse({"theme": theme})
    else:
        response = RedirectResponse(safe_next(next_url), status_code=303)
    response.set_cookie("theme", theme, max_age=365 * 24 * 3600, httponly=True,
                        samesite="lax", secure=settings.https_only)
    return response
