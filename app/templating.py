import hashlib
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from .config import settings
from .profile import THEMES

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Changes whenever style.css changes, so browsers never keep showing an old stylesheet.
templates.env.globals["css_version"] = hashlib.md5(
    (BASE_DIR / "static" / "style.css").read_bytes()
).hexdigest()[:10]


def flash(request: Request, message: str, category: str = "info") -> None:
    # Re-assign the list (instead of appending in place) so the session
    # middleware notices the change and saves the cookie.
    flashes = list(request.session.get("_flashes", []))
    flashes.append([category, message])
    request.session["_flashes"] = flashes


def render(request: Request, name: str, user=None, status_code: int = 200, **context):
    theme = user.theme if user else request.cookies.get("theme")
    context["theme"] = theme if theme in THEMES else "system"
    context["user"] = user
    context["is_admin"] = bool(user and user.username in settings.admin_usernames)
    context["flashes"] = request.session.pop("_flashes", [])
    return templates.TemplateResponse(request, name, context, status_code=status_code)
