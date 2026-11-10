"""Helpers for a link's activity log: the visitor's time zone and each day's link state."""

import re
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from urllib.parse import unquote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Request

from .models import Link, LinkToggle, as_utc

# e.g. "Asia/Kolkata", "America/Argentina/Buenos_Aires", "UTC":
# letters, digits, _ + - and up to 2 slashes.
_TZ_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_+\-]*(/[A-Za-z0-9_+\-]+){0,2}$")


def visitor_timezone(request: Request) -> tuple[tzinfo, str]:
    """The visitor's time zone, from the `tz` cookie that app.js sets. Falls back to UTC."""
    name = unquote(request.cookies.get("tz", ""))
    if 0 < len(name) <= 64 and _TZ_NAME.match(name):
        try:
            return ZoneInfo(name), name
        except (ZoneInfoNotFoundError, ValueError, OSError):
            pass
    return timezone.utc, "UTC"


def local_date(moment: datetime, tz: tzinfo) -> date:
    return as_utc(moment).astimezone(tz).date()


def day_window(day: date, tz: tzinfo) -> tuple[datetime, datetime]:
    """Start (included) and end (excluded) of a local calendar day, as UTC moments."""
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def _off_spans(toggles: list[LinkToggle]) -> list[tuple[datetime, datetime]]:
    """The stretches of time the owner had the link switched off (an open one lasts forever)."""
    spans, off_since = [], None
    for t in sorted(toggles, key=lambda t: as_utc(t.at)):
        if not t.active and off_since is None:
            off_since = as_utc(t.at)
        elif t.active and off_since is not None:
            spans.append((off_since, as_utc(t.at)))
            off_since = None
    if off_since is not None:
        spans.append((off_since, datetime.max.replace(tzinfo=timezone.utc)))
    return spans


def day_state(
    link: Link, day: date, tz: tzinfo, now: datetime, toggles: list[LinkToggle] = ()
) -> str:
    """What the link was doing on one local day.

    'active'     live for the whole day (or the whole part of it that has happened so far)
    'partial'    live for only part of that day (it started, ended or was switched during the day)
    'inactive'   the owner had it switched off for the whole day
    'scheduled'  not live yet that day (its start time came later)
    'expired'    no longer live that day (its end time had passed)

    Days before the link existed are not asked about. The schedule is the link's *current* one;
    the owner's on/off switching comes from the recorded `toggles`.
    """
    day_start, day_end = day_window(day, tz)
    seen_from = max(day_start, as_utc(link.created_at))
    seen_to = min(day_end, now)
    if seen_to <= seen_from:  # created a moment ago: look at a one-second slice
        seen_to = seen_from + timedelta(seconds=1)

    live_from = max(seen_from, as_utc(link.starts_at)) if link.starts_at else seen_from
    live_to = min(seen_to, as_utc(link.expires_at)) if link.expires_at else seen_to

    if live_to <= live_from:  # the schedule had it closed for that whole day
        if link.starts_at and as_utc(link.starts_at) >= seen_to:
            return "scheduled"
        return "expired"

    live = live_to - live_from
    for off_start, off_end in _off_spans(list(toggles)):
        overlap = min(off_end, live_to) - max(off_start, live_from)
        if overlap > timedelta(0):
            live -= overlap
    if live <= timedelta(0):
        return "inactive"
    if live >= seen_to - seen_from:
        return "active"
    return "partial"


def link_events(link: Link, now: datetime, toggles: list[LinkToggle] = ()) -> list[dict]:
    """Created / goes live / expires / switched off or on, oldest first.

    `future` marks the ones still to come. Only the 10 latest on/off switches are listed.
    """
    events = [{"key": "created", "at": as_utc(link.created_at), "future": False}]
    if link.starts_at:
        start = as_utc(link.starts_at)
        events.append({"key": "starts", "at": start, "future": start > now})
    if link.expires_at:
        end = as_utc(link.expires_at)
        events.append({"key": "expires", "at": end, "future": end > now})
    for t in sorted(toggles, key=lambda t: as_utc(t.at))[-10:]:
        events.append({"key": "on" if t.active else "off", "at": as_utc(t.at), "future": False})
    return sorted(events, key=lambda e: e["at"])
