import ipaddress
import re
import secrets
import string
from datetime import datetime, time, timezone
from urllib.parse import urlparse

BASE62 = string.ascii_letters + string.digits
RESERVED_USERNAMES = {
    "dashboard", "static", "login", "logout", "register", "docs", "redoc",
    "openapi", "health", "api", "admin", "www", "u", "links", "account", "settings", "profile",
    "language",
}
USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")
SLUG_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def generate_slug(length: int = 6) -> str:
    """Random base62 code, e.g. 'x7Kp2Q'. 62^6 = ~56 billion combinations."""
    return "".join(secrets.choice(BASE62) for _ in range(length))


def validate_username(username: str) -> str:
    username = username.strip().lower()
    if not USERNAME_RE.match(username):
        raise ValueError("Username must be 3-20 characters: letters, numbers, underscore.")
    if username in RESERVED_USERNAMES:
        raise ValueError("That username is reserved.")
    return username


def validate_email(email: str) -> str:
    email = email.strip().lower()
    if len(email) > 255 or not EMAIL_RE.match(email):
        raise ValueError("Enter a valid email address.")
    return email


def validate_password(password: str) -> str:
    # bcrypt only uses the first 72 bytes, so we cap it.
    if len(password) < 8 or len(password.encode()) > 72:
        raise ValueError("Password must be 8-72 characters.")
    return password


def validate_slug(slug: str) -> str:
    slug = slug.strip()
    if not SLUG_RE.match(slug):
        raise ValueError("Custom alias must be 3-32 characters: letters, numbers, - or _.")
    return slug


def validate_url(raw: str, blocked_hosts: tuple[str, ...] = ()) -> str:
    """Return a cleaned URL or raise ValueError. Blocks unsafe/local targets."""
    url = raw.strip()
    if not url:
        raise ValueError("Enter a URL.")
    if len(url) > 2048:
        raise ValueError("URL is too long (max 2048 characters).")
    if any(c.isspace() for c in url):
        raise ValueError("URL cannot contain spaces.")
    if "://" not in url:
        url = "https://" + url
    parts = urlparse(url)
    if parts.scheme not in ("http", "https"):
        raise ValueError("Only http and https links are allowed.")
    host = (parts.hostname or "").lower()
    if not host or "." not in host and host != "localhost":
        raise ValueError("That doesn't look like a valid URL.")
    try:
        _ = parts.port  # raises ValueError for a bad port
    except ValueError:
        raise ValueError("That URL has an invalid port.") from None
    if host == "localhost" or host.endswith(".local") or host in blocked_hosts:
        raise ValueError("That host is not allowed.")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip and (ip.is_private or ip.is_loopback or ip.is_link_local
               or ip.is_reserved or ip.is_multicast):
        raise ValueError("Private or local addresses are not allowed.")
    return url


def parse_device(user_agent: str | None) -> str:
    ua = (user_agent or "").lower()
    if any(w in ua for w in ("bot", "crawler", "spider", "preview")):
        return "bot"
    if "ipad" in ua or "tablet" in ua or ("android" in ua and "mobile" not in ua):
        return "tablet"
    if any(w in ua for w in ("mobi", "iphone", "android")):
        return "mobile"
    return "desktop"


def csv_safe(value: str) -> str:
    """Stop spreadsheet formula injection when the CSV is opened in Excel."""
    return "'" + value if value[:1] in ("=", "+", "-", "@") else value


_DISPLAY_RE = re.compile(
    r"(\d{1,2})/(\d{1,2})/(\d{4})"  # DD/MM/YYYY (a weekday name in front is ignored)
    r"(?:[\s,]+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp][Mm])?)?"  # optional time
)


def _parse_display(raw: str):
    """Read 'Sunday, 11/10/2026, 09:30:15 PM' (the format shown in the date picker)."""
    found = _DISPLAY_RE.search(raw)
    if not found:
        raise ValueError("That date or time is not valid.")
    day, month, year, hour, minute, second, ampm = found.groups()
    if hour is None:
        return datetime(int(year), int(month), int(day)), True
    hour = int(hour)
    if ampm:
        if not 1 <= hour <= 12:
            raise ValueError("That date or time is not valid.")
        hour = hour % 12 + (12 if ampm.lower() == "pm" else 0)
    return datetime(int(year), int(month), int(day), hour, int(minute), int(second or 0)), False


def parse_moment(utc_value: str, visible_value: str, *, end_of_day: bool = False):
    """Turn a form value into an aware UTC datetime (or None when blank).

    The browser sends the exact moment in UTC (``utc_value``). Without JavaScript we only
    get the visible field, which we read as UTC. It may be ISO text or the picker's format
    (``Sunday, 11/10/2026, 09:30:15 PM``). A bare date means the whole day: the start of it
    for a start time, the end of it for an end time.
    """
    raw = (utc_value or "").strip() or (visible_value or "").strip()
    if not raw:
        return None
    try:
        try:
            moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            date_only = "T" not in raw and " " not in raw
        except ValueError:
            moment, date_only = _parse_display(raw)
    except ValueError:
        raise ValueError("That date or time is not valid.") from None
    if date_only:
        moment = datetime.combine(moment.date(), time(23, 59, 59) if end_of_day else time.min)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    if not 2000 <= moment.year <= 2100:
        raise ValueError("That date or time is not valid.")
    return moment


def validate_link_password(password: str) -> str:
    if len(password) < 4 or len(password.encode()) > 72:
        raise ValueError("A link password must be 4-72 characters.")
    return password
