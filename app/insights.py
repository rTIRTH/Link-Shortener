"""Who is clicking: where they came from, what they use, where they are, and when.

Worked out from each click as it happens. A "visitor" is a salted hash of the address and the
browser, so repeat clicks can be told apart without ever storing an IP address.
"""

import hashlib
import ipaddress
import json
import re
from collections import Counter
from functools import lru_cache
from importlib import resources
from pathlib import Path
from urllib.parse import unquote

import httpx

from .cache import cache_get, cache_set
from .config import settings
from .i18n import WEEKDAYS, WEEKDAYS_SHORT, translate
from .models import as_utc
from .utils import parse_device

# ---- where the click came from -------------------------------------------------------------

# key -> (name shown, hosts it can come from, words an in-app browser puts in its user agent)
SOURCES = {
    "whatsapp": ("WhatsApp", ("whatsapp.com", "wa.me"), ("whatsapp",)),
    "instagram": ("Instagram", ("instagram.com",), ("instagram",)),
    "facebook": ("Facebook", ("facebook.com", "fb.com", "fb.me", "fb.watch"),
                 ("fban", "fbav", "fb_iab")),
    "messenger": ("Messenger", ("messenger.com", "m.me"), ("messenger",)),
    "x": ("X", ("twitter.com", "x.com", "t.co"), ("twitter",)),
    "linkedin": ("LinkedIn", ("linkedin.com", "lnkd.in"), ("linkedin",)),
    "youtube": ("YouTube", ("youtube.com", "youtu.be"), ()),
    "telegram": ("Telegram", ("t.me", "telegram.org", "telegram.me"), ("telegram",)),
    "reddit": ("Reddit", ("reddit.com", "redd.it"), ()),
    "snapchat": ("Snapchat", ("snapchat.com",), ("snapchat",)),
    "pinterest": ("Pinterest", ("pinterest.com", "pin.it"), ("pinterest",)),
    "github": ("GitHub", ("github.com",), ()),
    "bing": ("Bing", ("bing.com",), ()),
    "duckduckgo": ("DuckDuckGo", ("duckduckgo.com",), ()),
    "google": ("Google", (), ()),  # google.<anything>, handled in classify_source
}
EMAIL_HOSTS = (
    "mail.google.com", "outlook.live.com", "outlook.office.com", "outlook.office365.com",
    "mail.yahoo.com", "mail.proton.me",
)
# What a person may write after ?ref= to name the place they shared the link.
TAG_ALIASES = {
    "twitter": "x", "ig": "instagram", "fb": "facebook", "wa": "whatsapp", "yt": "youtube",
    "tg": "telegram", "mail": "email", "newsletter": "email", "gmail": "email",
}
# Android apps send "android-app://<package>" as the referrer, so the "host" is the package name.
ANDROID_APPS = {
    "com.google.android.gm": "email", "com.google.android.googlequicksearchbox": "google",
    "com.whatsapp": "whatsapp", "com.whatsapp.w4b": "whatsapp",
    "com.instagram.android": "instagram",
    "com.facebook.katana": "facebook", "com.facebook.orca": "messenger",
    "org.telegram.messenger": "telegram", "com.twitter.android": "x",
    "com.linkedin.android": "linkedin", "com.reddit.frontpage": "reddit",
    "com.snapchat.android": "snapchat", "com.pinterest": "pinterest",
}
_GOOGLE = re.compile(r"(^|\.)google\.(com|co\.[a-z]{2}|com\.[a-z]{2}|[a-z]{2,3})$")


def _on(host: str, names: tuple[str, ...]) -> bool:
    return any(host == n or host.endswith("." + n) for n in names)


def classify_source(host: str | None, user_agent: str | None = None, tag: str | None = None) -> str:
    """'whatsapp', 'instagram', ... 'email', 'website' (some other site) or 'direct'."""
    host = (host or "").lower().split(":")[0]
    ua = (user_agent or "").lower()
    tag = (tag or "").strip().lower()[:40]
    tag = TAG_ALIASES.get(tag, tag)
    if tag in SOURCES or tag == "email":  # the owner named it: that wins
        return tag
    if host:
        if host in ANDROID_APPS:
            return ANDROID_APPS[host]
        if _on(host, EMAIL_HOSTS):
            return "email"
        for key, (_name, hosts, _words) in SOURCES.items():
            if hosts and _on(host, hosts):
                return key
        if _GOOGLE.search(host):
            return "google"
    for key, (_name, _hosts, words) in SOURCES.items():  # in-app browsers often send no referrer
        if any(w in ua for w in words):
            return key
    return "website" if host else "direct"


def source_label(lang: str, key: str | None) -> str:
    if key in SOURCES:
        return SOURCES[key][0]  # brand names are not translated
    names = {"direct": "Direct", "email": "Email", "website": "Other websites"}
    return translate(lang, names.get(key or "", "Other"))


# ---- what they used ---------------------------------------------------------------------------

BROWSERS = {
    "edge": "Edge", "opera": "Opera", "samsung": "Samsung Internet", "firefox": "Firefox",
    "chrome": "Chrome", "safari": "Safari",
}
SYSTEMS = {
    "windows": "Windows", "android": "Android", "ios": "iOS", "macos": "macOS",
    "linux": "Linux", "chromeos": "ChromeOS",
}
_IN_APP = (
    "instagram", "fban", "fbav", "fb_iab", "linkedinapp", "snapchat", "micromessenger",
    "telegram", "twitter", "pinterest", "whatsapp", "line/",
)


def _browser(ua: str, device: str) -> str:
    if not ua:
        return "unknown"
    if device == "bot":
        return "other"
    if any(w in ua for w in _IN_APP):
        return "inapp"
    if "edg/" in ua or "edga/" in ua or "edgios/" in ua:
        return "edge"
    if "opr/" in ua or "opera" in ua:
        return "opera"
    if "samsungbrowser" in ua:
        return "samsung"
    if "firefox/" in ua or "fxios" in ua:
        return "firefox"
    if "chrome/" in ua or "crios" in ua:
        return "chrome"
    if "safari/" in ua:
        return "safari"
    return "other"


def _system(ua: str) -> str:
    if not ua:
        return "unknown"
    if "iphone" in ua or "ipad" in ua or "ipod" in ua:
        return "ios"
    if "android" in ua:
        return "android"
    if "cros" in ua:
        return "chromeos"
    if "windows" in ua:
        return "windows"
    if "macintosh" in ua or "mac os x" in ua:
        return "macos"
    if "linux" in ua or "x11" in ua:
        return "linux"
    return "other"


def parse_agent(user_agent: str | None) -> tuple[str, str, str]:
    """(device, browser, operating system) as short keys, e.g. ('mobile', 'chrome', 'android')."""
    ua = (user_agent or "").lower()
    device = parse_device(user_agent)
    return device, _browser(ua, device), _system(ua)


def browser_label(lang: str, key: str | None) -> str:
    if key in BROWSERS:
        return BROWSERS[key]
    return translate(lang, {"inapp": "In-app browser", "other": "Other"}.get(key or "", "Unknown"))


def system_label(lang: str, key: str | None) -> str:
    if key in SYSTEMS:
        return SYSTEMS[key]
    return translate(lang, "Unknown" if key in (None, "unknown") else "Other")


def device_label(lang: str, key: str | None) -> str:
    return translate(lang, key if key in ("desktop", "mobile", "tablet", "bot") else "Unknown")


# ---- where they are ---------------------------------------------------------------------------

_COUNTRY_HEADERS = (
    "cf-ipcountry", "cloudfront-viewer-country", "x-vercel-ip-country", "x-appengine-country",
    "x-country-code",
)
_CITY_HEADERS = ("cf-ipcity", "cloudfront-viewer-city", "x-vercel-ip-city", "x-appengine-city")


def clean_country(code: str | None) -> str | None:
    code = (code or "").strip().upper()
    return code if re.fullmatch(r"[A-Z]{2}", code) and code not in ("XX", "T1", "ZZ") else None


def clean_city(name: str | None) -> str | None:
    name = unquote(name or "").strip()[:80]
    return name if name and name.lower() not in ("unknown", "null", "none") else None


def geo_from_headers(headers) -> tuple[str | None, str | None]:
    """The country and city the hosting service already worked out, if it did."""
    country = next((c for h in _COUNTRY_HEADERS if (c := clean_country(headers.get(h)))), None)
    city = next((c for h in _CITY_HEADERS if (c := clean_city(headers.get(h)))), None)
    return (country, city if country else None)


def client_address(headers, fallback: str | None) -> str | None:
    """The visitor's address behind the hosting proxy (used for the hash and the lookup only)."""
    for name in ("true-client-ip", "cf-connecting-ip"):
        if headers.get(name):
            return headers[name].strip()[:64]
    address = headers.get("x-forwarded-for", "").split(",")[0].strip() or fallback
    return address[:64] if address else None


def _is_public(address: str | None) -> bool:
    try:
        return bool(address) and ipaddress.ip_address(address).is_global
    except ValueError:
        return False


def lookup_geo(address: str | None) -> tuple[str | None, str | None]:
    """Country and city of a public IP address, from a free lookup service. Never raises.

    Cached, so a busy visitor costs one request a week. Runs after the redirect has been sent.
    """
    if not settings.geo_lookup or not _is_public(address):
        return None, None
    key = f"geo:{address}"
    raw = cache_get(key)
    if raw:
        country, city = json.loads(raw)
        return country, city
    country = city = None
    ttl = 300  # a failed lookup is retried after five minutes
    try:
        data = httpx.get(settings.geo_url.format(ip=address), timeout=1.5).json()
        if data.get("status") == "success":
            country, city = clean_country(data.get("countryCode")), clean_city(data.get("city"))
            ttl = 7 * 24 * 3600
    except (httpx.HTTPError, ValueError, AttributeError):
        pass
    cache_set(key, json.dumps([country, city]), ttl)
    return country, city


@lru_cache(maxsize=1)
def country_names() -> dict[str, str]:
    """ISO code -> English name, from the tz database that ships with the `tzdata` package."""
    try:
        text = resources.files("tzdata.zoneinfo").joinpath("iso3166.tab").read_text("utf-8")
    except (ModuleNotFoundError, FileNotFoundError, OSError):
        try:
            text = Path("/usr/share/zoneinfo/iso3166.tab").read_text("utf-8")
        except OSError:
            return {}
    pairs = (line.split("\t", 1) for line in text.splitlines() if line and line[0] != "#")
    return {code: name.strip() for code, name in (p for p in pairs if len(p) == 2)}


def country_name(code: str) -> str:
    return country_names().get(code, code)


def visitor_id(address: str | None, user_agent: str | None) -> str:
    """The same person on the same device and network gives the same id. The IP is not kept."""
    raw = f"{settings.secret_key}|{address or ''}|{user_agent or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---- turning clicks into the numbers on the page -----------------------------------------------


def rank_rows(counter: Counter, label, *, limit: int = 8, code=None) -> list[dict]:
    """The biggest entries, each with its share of the total and a bar width (biggest = 100)."""
    total = sum(counter.values())
    items = counter.most_common(limit)
    peak = items[0][1] if items else 1
    return [
        {
            "key": key, "label": label(key), "n": n, "code": code(key) if code else None,
            "pct": round(100 * n / total) if total else 0, "width": max(3, round(100 * n / peak)),
        }
        for key, n in items
    ]


def day_index(moment, tz) -> tuple[int, int]:
    """(weekday with Monday = 0, hour) of a click, in the visitor's time zone."""
    local = as_utc(moment).astimezone(tz)
    return local.weekday(), local.hour


def weekday_name(lang: str, monday_first: int, *, short: bool = False) -> str:
    table = WEEKDAYS_SHORT if short else WEEKDAYS
    return table.get(lang, table["en"])[(monday_first + 1) % 7]  # the lists start on Sunday


def audience(rows, tz, lang: str) -> dict:
    """Everything the audience section shows, for the clicks in `rows` (newest data first)."""
    rows = list(rows)
    visitors = Counter(r.visitor for r in rows if r.visitor)
    tracked = sum(visitors.values())
    grid = [[0] * 24 for _ in range(7)]
    for r in rows:
        day, hour = day_index(r.clicked_at, tz)
        grid[day][hour] += 1

    sources = Counter(
        r.source or classify_source(r.referrer) for r in rows
    )
    places = Counter(
        (r.city, r.country) for r in rows if r.city and r.country
    )
    countries = Counter(r.country for r in rows if r.country)
    located = sum(countries.values())

    peak = max((n for line in grid for n in line), default=0)
    best = None
    if peak:
        day, hour = next((d, h) for d in range(7) for h in range(24) if grid[d][h] == peak)
        best = {"day": day, "hour": hour}

    return {
        "total": len(rows),
        "unique": len(visitors),
        "returning": sum(1 for n in visitors.values() if n > 1),
        "untracked": len(rows) - tracked,
        "sources": rank_rows(sources, lambda k: source_label(lang, k)),
        "devices": rank_rows(Counter(r.device for r in rows), lambda k: device_label(lang, k),
                             limit=6),
        "browsers": rank_rows(Counter(r.browser or "unknown" for r in rows),
                              lambda k: browser_label(lang, k), limit=6),
        "systems": rank_rows(Counter(r.os or "unknown" for r in rows),
                             lambda k: system_label(lang, k), limit=6),
        "countries": rank_rows(countries, country_name, code=lambda k: k),
        "cities": rank_rows(places, lambda k: k[0], code=lambda k: k[1]),
        "no_location": len(rows) - located,
        "grid": grid,
        "peak": peak,
        "best": best,
    }
