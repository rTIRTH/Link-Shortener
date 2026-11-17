"""Campaign tracking tags (utm_source and friends) added to a destination address.

The create form and the Edit page have boxes for them. The finished address is what is stored,
so redirects, the link check and Export CSV all see the real destination. On the Edit page the
tags are taken back out of the address box and shown in their own boxes again.
"""

from urllib.parse import quote, unquote_plus, urlsplit, urlunsplit

UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")
MAX_UTM_LENGTH = 100


def clean_value(raw: str | None) -> str:
    """One tag value from a box: trimmed and single-spaced. ValueError if it is too long."""
    value = " ".join((raw or "").split())
    if len(value) > MAX_UTM_LENGTH or any(ord(c) < 32 for c in value):
        raise ValueError("Each tracking tag can be up to 100 characters.")
    return value


def _key(pair: str) -> str:
    return unquote_plus(pair.split("=", 1)[0]).lower()


def split_utm(url: str) -> tuple[str, dict[str, str]]:
    """(the address without its utm_* tags, the tags it had). Other parts are left untouched."""
    parts = urlsplit(url)
    pairs = [p for p in parts.query.split("&") if p]
    found: dict[str, str] = {}
    kept = []
    for pair in pairs:
        key = _key(pair)
        if key in UTM_KEYS:
            found.setdefault(key, unquote_plus(pair.split("=", 1)[1]) if "=" in pair else "")
        else:
            kept.append(pair)
    if not found:
        return url, {}
    return urlunsplit(parts._replace(query="&".join(kept))), {k: v for k, v in found.items() if v}


def with_utm(url: str, tags: dict[str, str]) -> str:
    """The address with these tags added at the end of its query (empty values are left out)."""
    extra = [f"{k}={quote(tags[k], safe='')}" for k in UTM_KEYS if tags.get(k)]
    if not extra:
        return url
    parts = urlsplit(url)
    query = "&".join([q for q in (parts.query, *extra) if q])
    return urlunsplit(parts._replace(query=query))


def merge(url: str, boxes: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Tags typed into the address itself, overridden by anything typed in the boxes.

    Returns (address without tags, the tags that will be used).
    """
    clean, typed = split_utm(url)
    return clean, {**typed, **{k: v for k, v in boxes.items() if v}}
