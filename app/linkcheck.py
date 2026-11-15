"""Looks at a destination before a link is made.

Two questions, answered in this order:
  1. Is the address known to be unsafe? (your own BLOCKED_DOMAINS list, and Google Safe Browsing
     when SAFE_BROWSING_API_KEY is set.) Such addresses are refused.
  2. Does it answer? A quick request tells us. A site that does not answer only earns a warning,
     because it may be down for a moment, so the link is still made.

Nothing here can break link creation: every failure just means "could not tell".
"""

import ipaddress
import socket
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

from .config import settings

UNSAFE_MESSAGE = "This web address is on a list of unsafe sites, so it can't be shortened."
NO_ANSWER_MESSAGE = (
    "Heads up: that address did not answer when we checked it. The link was saved anyway, "
    "but please make sure the address is correct."
)
SAFE_BROWSING_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
REDIRECT_CODES = (301, 302, 303, 307, 308)
MAX_HOPS = 5
_TRANSPORT: httpx.BaseTransport | None = None  # tests put a fake network here


@dataclass(frozen=True)
class Check:
    verdict: str  # "ok", "unreachable", "blocked" or "skipped" (checking is switched off)
    reason: str = ""  # a short English note for the logs and the tests


def host_blocked(host: str) -> bool:
    """True if the host, or a parent domain of it, is on the owner's blocklist."""
    host = (host or "").lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in settings.blocked_domains)


def safe_browsing_hit(url: str) -> bool:
    """Ask Google Safe Browsing about the address. False if there is no key or no answer."""
    if not settings.safe_browsing_key:
        return False
    body = {
        "client": {"clientId": "link-shortener", "clientVersion": "1.0"},
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }
    try:
        with httpx.Client(timeout=2.5, transport=_TRANSPORT) as client:
            reply = client.post(
                SAFE_BROWSING_URL, params={"key": settings.safe_browsing_key}, json=body
            )
        return bool(reply.json().get("matches"))
    except (httpx.HTTPError, ValueError, AttributeError):
        return False


def _addresses(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    found = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return [ipaddress.ip_address(item[4][0].split("%")[0]) for item in found]


def probe(url: str) -> str:
    """'ok', 'down' (does not answer, or an error page) or 'unsure' (could not tell).

    Redirects are followed by hand, a few steps, and every step's host is checked first: the
    server never calls an address that points into a private network.
    """
    started = time.monotonic()
    headers = {"User-Agent": "LinkShortenerCheck/1.0 (checks that a link works)"}
    with httpx.Client(
        timeout=settings.link_check_timeout, follow_redirects=False, headers=headers,
        transport=_TRANSPORT,
    ) as client:
        for _hop in range(MAX_HOPS):
            if time.monotonic() - started > settings.link_check_budget:
                return "unsure"
            parts = urlparse(url)
            if parts.scheme not in ("http", "https") or not parts.hostname:
                return "unsure"
            try:
                addresses = _addresses(parts.hostname)
            except socket.gaierror:
                return "down"  # the name does not exist
            except (OSError, ValueError):
                return "unsure"
            if not addresses or not all(a.is_global for a in addresses):
                return "unsure"  # points inside a private network: never touch it
            try:
                with client.stream("GET", url) as reply:
                    code, location = reply.status_code, reply.headers.get("location")
            except httpx.HTTPError:
                return "down"  # refused, reset, or too slow
            if code in REDIRECT_CODES and location:
                url = urljoin(url, location)
                continue
            # 404/410 and server errors mean a broken link. Other refusals (401, 403, 429 ...)
            # are often just a site that dislikes robots, so they are not held against it.
            return "down" if code in (404, 410) or code >= 500 else "ok"
    return "unsure"


def check_destination(url: str) -> Check:
    host = urlparse(url).hostname or ""
    if host_blocked(host):
        return Check("blocked", "blocklist")
    if not settings.link_check:
        return Check("skipped")
    if safe_browsing_hit(url):
        return Check("blocked", "safe browsing")
    return Check("unreachable", "no answer") if probe(url) == "down" else Check("ok")
