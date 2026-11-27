"""Bulk: change the same settings on many links at once (and add many from a file).

The person ticks the links, then ticks "Change this" next to each setting they want to change.
Everything is checked before any link is touched; a link is then either changed completely or,
if the new settings do not fit it, left exactly as it was (and counted in a message).
"""
from collections import Counter

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import alerts
from ..cache import cache_delete, rate_limit
from ..database import get_db
from ..deps import require_user
from ..features import require
from ..mailer import email_enabled
from ..models import LinkToggle, User, UsernameAlias, as_utc, utcnow
from ..qr import DEFAULT_BG, DEFAULT_FG, check_colors, parse_color
from ..security import hash_password
from ..tags import clean_tag, tag_color
from ..templating import flash, render
from ..utils import (
    parse_click_limit,
    parse_moment,
    parse_preview_message,
    validate_link_password,
)
from .dashboard import cache_key, short_url, tag_chips, user_links

router = APIRouter(prefix="/dashboard/bulk")

MAX_BULK = 200  # most links one press of the button may change
SETTINGS = ("password", "start", "end", "limit", "status", "preview", "alerts", "qr")


@router.get("")
def bulk_page(
    request: Request,
    tag: str = Query(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    links = user_links(db, user, archived=False)
    tag_name = clean_tag(tag)
    tag_counts = Counter(t.name for link in links for t in link.tags)
    shown = [x for x in links if tag_name in {t.name for t in x.tags}] if tag_name else links
    return render(
        request, "bulk.html", user,
        rows=[{"link": x, "short_url": short_url(request, user, x), "tags": tag_chips(x)}
              for x in shown],
        tag_name=tag_name, max_bulk=MAX_BULK, email_ready=email_enabled(),
        qr_fg=DEFAULT_FG, qr_bg=DEFAULT_BG,
        tag_bar=[{"name": n, "count": c, "color": tag_color(n)}
                 for n, c in sorted(tag_counts.items())],
    )


def forget_links(db: Session, user: User, slugs: list[str]) -> None:
    """Visitors must see the new settings straight away: drop the links from the cache."""
    names = [user.username, *db.scalars(
        select(UsernameAlias.username).where(UsernameAlias.user_id == user.id))]
    for slug in slugs:
        for name in names:
            cache_delete(cache_key(name, slug))


@router.post("")
def bulk_apply(
    request: Request,
    ids: list[int] = Form(default=[]),
    change_password: str = Form(""), password_action: str = Form("set"),
    new_password: str = Form(""),
    change_start: str = Form(""), starts_at: str = Form(""), starts_at_utc: str = Form(""),
    change_end: str = Form(""), expires_at: str = Form(""), expires_at_utc: str = Form(""),
    change_limit: str = Form(""), click_limit: str = Form(""),
    change_status: str = Form(""), status: str = Form("on"),
    change_preview: str = Form(""), preview: str = Form(""), preview_message: str = Form(""),
    change_alerts: str = Form(""), alert_limit: str = Form(""), alert_expiry: str = Form(""),
    alert_clicks: str = Form(""),
    change_qr: str = Form(""), qr_action: str = Form("set"),
    qr_fg: str = Form(DEFAULT_FG), qr_bg: str = Form(DEFAULT_BG),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    def back(message: str, kind: str = "error", **params):
        flash(request, message, kind, **params)
        return RedirectResponse("/dashboard/bulk", status_code=303)

    ticked = {
        "password": change_password, "start": change_start, "end": change_end,
        "limit": change_limit, "status": change_status, "preview": change_preview,
        "alerts": change_alerts, "qr": change_qr,
    }
    wants = {name: ticked[name] == "1" for name in SETTINGS}
    chosen = list(dict.fromkeys(ids))
    try:
        require(user, "bulk_edit")
    except ValueError as e:
        return back(str(e))
    if not chosen:
        return back("Select at least one link first.")
    if len(chosen) > MAX_BULK:
        return back("You can change up to {n} links at once.", n=MAX_BULK)
    if not any(wants.values()):
        return back("Choose at least one thing to change.")
    if not rate_limit(f"rl:bulk:{user.id}", 10, 60):
        return back("Too many attempts. Try again later.")

    # 1. Check every choice once, before any link is touched. A mistake changes nothing.
    new_hash = start = end = limit = note = fg = bg = None
    show = reset = on_limit = on_expiry = False
    try:
        if wants["password"]:
            if password_action == "set":
                new_hash = hash_password(validate_link_password(new_password))
            elif password_action == "remove":
                new_hash = None
            else:
                raise ValueError("Unknown password option.")
        if wants["start"]:
            start = parse_moment(starts_at_utc, starts_at)
        if wants["end"]:
            end = parse_moment(expires_at_utc, expires_at, end_of_day=True)
        if wants["start"] and wants["end"] and start and end and start >= end:
            raise ValueError("The end time must be after the start time.")
        if wants["limit"]:
            limit = parse_click_limit(click_limit)
            if limit is not None:  # taking a limit off is always allowed; putting one on is not
                require(user, "click_limit")
        if wants["preview"]:
            show = preview == "1"
            note = parse_preview_message(preview_message) if show else None
            if show:
                require(user, "preview")
        if wants["alerts"]:
            on_limit, on_expiry = alert_limit == "1", alert_expiry == "1"
            if on_limit or on_expiry or alerts.parse_alert_clicks(alert_clicks) is not None:
                require(user, "alerts")
        if wants["qr"]:
            reset = qr_action == "reset"  # back to the plain code: always allowed
            if not reset:
                fg, bg = parse_color(qr_fg), parse_color(qr_bg)
                check_colors(fg, bg)
                if (fg, bg) != (DEFAULT_FG, DEFAULT_BG):
                    require(user, "qr_style")
    except ValueError as e:
        return back(str(e))
    links = user_links(db, user, chosen)  # only the person's own links can match
    if not links:
        return back("Select at least one link first.")

    # 2. Change the links one by one. A link the new settings do not fit is left alone.
    changed, bad_schedule, bad_alerts, done = 0, 0, 0, []
    for link in links:
        new_start = start if wants["start"] else link.starts_at
        new_end = end if wants["end"] else link.expires_at
        if (wants["start"] or wants["end"]) and new_start and new_end \
                and as_utc(new_start) >= as_utc(new_end):
            bad_schedule += 1
            continue
        new_limit = limit if wants["limit"] else link.click_limit
        alert = (link.alert_limit, link.alert_expiry, link.alert_clicks)
        if wants["alerts"]:
            try:
                alert = alerts.read_alert_settings(
                    on_limit, on_expiry, alert_clicks, limit=new_limit, end=new_end,
                    used=link.click_count, old_clicks=link.alert_clicks,
                )
            except ValueError:
                bad_alerts += 1
                continue
        alerts.apply_alert_settings(  # whatever changed is armed again, so it can be sent again
            link, *alert, limit_changed=new_limit != link.click_limit,
            end_changed=not alerts.same_moment(new_end, link.expires_at),
        )
        if wants["password"]:
            link.password_hash = new_hash
        if wants["start"]:
            link.starts_at = start
        if wants["end"]:
            link.expires_at = end
        if wants["limit"] and limit != link.click_limit:  # a new limit starts afresh
            link.limit_reached_at = None
            if limit is not None and link.click_count >= limit:
                link.limit_reached_at = utcnow()
            link.click_limit = limit
        if wants["status"] and link.is_active != (status != "off"):
            link.is_active = status != "off"
            link.toggles.append(LinkToggle(active=link.is_active))
        if wants["preview"]:
            link.preview, link.preview_message = show, note
        if wants["qr"]:
            if reset:
                link.qr_fg = link.qr_bg = link.qr_logo = None
            else:
                link.qr_fg = fg if fg != DEFAULT_FG else None
                link.qr_bg = bg if bg != DEFAULT_BG else None
        changed += 1
        done.append(link.slug)
    db.commit()
    forget_links(db, user, done)

    if changed:
        flash(request, "Changed {n} link(s).", "success", n=changed)
    else:
        flash(request, "No links were changed.", "warn")
    if bad_schedule:
        flash(request, "{n} link(s) were skipped because their start time would not be before "
                       "their end time.", "warn", n=bad_schedule)
    if bad_alerts:
        flash(request, "{n} link(s) were skipped because the alerts you chose do not fit them: "
                       "an alert needs a click limit or an end time, and a number of clicks must "
                       "be higher than the clicks so far.", "warn", n=bad_alerts)
    return RedirectResponse("/dashboard/bulk", status_code=303)
