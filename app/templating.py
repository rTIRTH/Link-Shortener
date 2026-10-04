from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from .config import settings

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def flash(request: Request, message: str, category: str = "info") -> None:
    # Re-assign the list (instead of appending in place) so the session
    # middleware notices the change and saves the cookie.
    flashes = list(request.session.get("_flashes", []))
    flashes.append([category, message])
    request.session["_flashes"] = flashes


def render(request: Request, name: str, user=None, status_code: int = 200, **context):
    context["user"] = user
    context["is_admin"] = bool(user and user.username in settings.admin_usernames)
    context["flashes"] = request.session.pop("_flashes", [])
    return templates.TemplateResponse(request, name, context, status_code=status_code)
