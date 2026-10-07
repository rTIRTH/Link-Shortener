import hashlib
from datetime import timezone
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from .config import settings
from .profile import THEMES

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Changes whenever style.css changes, so browsers never keep showing an old stylesheet.
def _version(*names: str) -> str:
    digest = hashlib.md5()
    for name in names:
        digest.update((BASE_DIR / "static" / name).read_bytes())
    return digest.hexdigest()[:10]


templates.env.globals["css_version"] = _version("style.css")
templates.env.globals["js_version"] = _version("app.js", "datetime-picker.js")


def _utc(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# Times are stored in UTC. The page shows the UTC text, then app.js swaps in local time.
templates.env.filters["utc_iso"] = lambda dt: _utc(dt).isoformat() if dt else ""
templates.env.filters["utc_text"] = lambda dt: _utc(dt).strftime("%d %b %Y %H:%M UTC") if dt else ""
templates.env.filters["utc_pretty"] = (
    lambda dt: _utc(dt).strftime("%A, %d/%m/%Y, %I:%M:%S %p") if dt else ""
)
templates.env.filters["utc_input"] = lambda dt: _utc(dt).strftime("%Y-%m-%dT%H:%M") if dt else ""


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
