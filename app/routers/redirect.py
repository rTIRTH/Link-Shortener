import json
import logging
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from ..cache import cache_get, cache_set, rate_limit
from ..config import settings
from ..database import get_db
from ..deps import client_ip
from ..insights import (
    classify_source,
    client_address,
    geo_from_headers,
    lookup_geo,
    parse_agent,
    visitor_id,
)
from ..models import Click, Link, User, UsernameAlias, as_utc, utcnow
from ..security import verify_password
from ..templating import render
from ..utils import parse_device
from .dashboard import cache_key

router = APIRouter()
log = logging.getLogger("linkshortener")

PREVIEW_TOKEN_SECONDS = 15 * 60  # how long the Continue button on a preview page stays valid


def _signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt="preview-continue")


def record_click(
    factory: sessionmaker,
    link_id: int,
    user_agent: str | None,
    referrer: str | None,
    address: str | None = None,
    geo: tuple[str | None, str | None] = (None, None),
    tag: str | None = None,
    counted: bool = False,
):
    """Runs AFTER the redirect is sent, so analytics never slow the visitor down.

    `counted` means the link's click counter was already raised (links with a click limit raise
    it before redirecting, so two visitors can never both take the last click).

    The address is only used for the country lookup and a one-way visitor id; it is not stored.
    """
    try:
        with factory() as db:
            host = None
            if referrer:
                host = urlparse(referrer).netloc[:255] or None
            device, browser, system = parse_agent(user_agent)
            country, city = geo if geo[0] else lookup_geo(address)
            db.add(Click(
                link_id=link_id, device=device, referrer=host,
                source=classify_source(host, user_agent, tag), browser=browser, os=system,
                country=country, city=city, visitor=visitor_id(address, user_agent),
            ))
            if not counted:
                db.execute(
                    update(Link).where(Link.id == link_id).values(click_count=Link.click_count + 1)
                )
            db.commit()
    except Exception:  # analytics must never break redirects
        log.exception("Failed to record click for link %s", link_id)


def load_link(db: Session, username: str, slug: str) -> dict:
    """The small record needed to serve a link. Cached in Redis, so hits skip the database."""
    key = cache_key(username, slug)
    raw = cache_get(key)
    if raw:
        return json.loads(raw)

    link = db.scalar(select(Link).join(User).where(User.username == username, Link.slug == slug))
    if not link:  # maybe the owner renamed themselves: old usernames still work
        link = db.scalar(
            select(Link)
            .join(UsernameAlias, UsernameAlias.user_id == Link.user_id)
            .where(UsernameAlias.username == username, Link.slug == slug)
        )
    if not link:
        raise HTTPException(404, "This short link does not exist.")

    expires = as_utc(link.expires_at) if link.expires_at else None
    starts = as_utc(link.starts_at) if link.starts_at else None
    data = {
        "id": link.id,
        "url": link.original_url,
        "exp": expires.isoformat() if expires else None,
        "start": starts.isoformat() if starts else None,
        "locked": bool(link.password_hash),  # the hash itself is never cached
        "off": not link.is_active,  # the owner switched it off
        "limit": link.click_limit,  # how many clicks it may have (the count itself is not cached)
        "preview": bool(link.preview),  # show "You're going to ..." before redirecting
        "note": link.preview_message,  # the owner's message on that page
    }
    ttl = settings.cache_ttl
    if expires:
        ttl = max(1, min(ttl, int((expires - utcnow()).total_seconds())))
    cache_set(key, json.dumps(data), ttl)
    return data


def check_window(data: dict) -> None:
    """Raise if the link is switched off, has expired, or has not started yet."""
    if data.get("off"):
        raise HTTPException(403, "This short link is turned off.")
    now = utcnow()
    if data.get("exp") and datetime.fromisoformat(data["exp"]) <= now:
        raise HTTPException(410, "This short link has expired.")
    if data.get("start") and datetime.fromisoformat(data["start"]) > now:
        raise HTTPException(403, "This short link is not active yet. Please check back later.")


def limit_reached(db: Session, link_id: int) -> bool:
    """True if the link has a click limit and has used it up."""
    return bool(db.scalar(select(Link.click_count >= Link.click_limit).where(Link.id == link_id)))


def take_click(
    db: Session, background: BackgroundTasks, request: Request, data: dict
) -> None:
    """Count this visit, or raise 410 when the link has no clicks left.

    Links with a limit reserve their click right here with one atomic UPDATE, so with one click
    left only one of two simultaneous visitors gets it. Link-preview robots (WhatsApp, Slack, ...)
    are let through without using a click, so sharing a one-time link does not burn it.
    """
    if data.get("limit") is None:
        count_click(background, request, data["id"])
        return
    if parse_device(request.headers.get("user-agent")) == "bot":
        if limit_reached(db, data["id"]):
            raise HTTPException(410, "This short link has reached its click limit.")
        return
    taken = db.execute(
        update(Link)
        .where(Link.id == data["id"], Link.click_count < Link.click_limit)
        .values(click_count=Link.click_count + 1)
        .returning(Link.click_count, Link.click_limit)
    ).first()
    if taken is None:
        db.rollback()
        raise HTTPException(410, "This short link has reached its click limit.")
    if taken.click_count >= taken.click_limit:  # that was the last one: remember when
        db.execute(update(Link).where(Link.id == data["id"]).values(limit_reached_at=utcnow()))
    db.commit()
    count_click(background, request, data["id"], counted=True)


def count_click(
    background: BackgroundTasks, request: Request, link_id: int, counted: bool = False
) -> None:
    background.add_task(
        record_click,
        request.app.state.session_factory,
        link_id,
        request.headers.get("user-agent"),
        request.headers.get("referer"),
        client_address(request.headers, request.client.host if request.client else None),
        geo_from_headers(request.headers),
        request.query_params.get("ref") or request.query_params.get("utm_source"),
        counted,
    )


def viewer(request: Request, db: Session) -> User | None:
    """The logged-in user (only looked up when we render a page, never on plain redirects)."""
    user_id = request.session.get("user_id")
    return db.get(User, user_id) if user_id else None


def preview_page(request: Request, db: Session, data: dict, username: str, slug: str):
    """The page shown before the redirect. Nothing is counted until the visitor presses Continue.

    The Continue button carries a signed, short-lived token. For a password-protected link the
    token is only handed out after the password, so it cannot be skipped.
    """
    if data.get("limit") is not None and limit_reached(db, data["id"]):
        raise HTTPException(410, "This short link has reached its click limit.")
    response = render(
        request, "preview.html", viewer(request, db), username=username, slug=slug,
        host=urlparse(data["url"]).hostname or "", url=data["url"], note=data.get("note"),
        token=_signer().dumps(data["id"]),
    )
    response.headers["X-Robots-Tag"] = "noindex"
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/{username}/{slug}")
def follow(
    username: str,
    slug: str,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    username = username.lower()
    data = load_link(db, username, slug)
    check_window(data)
    if data.get("locked"):  # show the password form, never the destination
        if data.get("limit") is not None and limit_reached(db, data["id"]):
            raise HTTPException(410, "This short link has reached its click limit.")
        return render(request, "unlock.html", viewer(request, db), username=username, slug=slug)
    if data.get("preview"):
        return preview_page(request, db, data, username, slug)
    take_click(db, background, request, data)
    return RedirectResponse(data["url"], status_code=302)


@router.post("/{username}/{slug}/continue")
def continue_to_destination(
    username: str,
    slug: str,
    request: Request,
    background: BackgroundTasks,
    token: str = Form(""),
    db: Session = Depends(get_db),
):
    """The Continue button of a preview page: count the visit and go on to the destination."""
    username = username.lower()
    data = load_link(db, username, slug)
    check_window(data)
    try:
        valid = _signer().loads(token, max_age=PREVIEW_TOKEN_SECONDS) == data["id"]
    except BadSignature:
        valid = False
    if not valid:  # no preview was shown (or it is too old): start again from the link
        return RedirectResponse(f"/{username}/{slug}", status_code=303)
    take_click(db, background, request, data)
    return RedirectResponse(data["url"], status_code=302)


@router.post("/{username}/{slug}")
def unlock(
    username: str,
    slug: str,
    request: Request,
    background: BackgroundTasks,
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    username = username.lower()
    data = load_link(db, username, slug)
    check_window(data)
    page = f"/{username}/{slug}"
    if not data.get("locked"):
        return RedirectResponse(page, status_code=303)

    # Limit guesses per visitor and link (works even without Redis)
    if not rate_limit(f"rl:unlock:{client_ip(request)}:{data['id']}", 5, 60, local_fallback=True):
        return render(request, "unlock.html", viewer(request, db), status_code=429,
                      username=username, slug=slug,
                      error="Too many attempts. Please wait a minute and try again.")

    stored = db.scalar(select(Link.password_hash).where(Link.id == data["id"]))
    if stored is None:  # the password was removed a moment ago
        return RedirectResponse(page, status_code=303)
    if not verify_password(password, stored):
        return render(request, "unlock.html", viewer(request, db), status_code=403,
                      username=username, slug=slug, error="Wrong password. Try again.")

    if data.get("preview"):  # the right password: now the preview, then Continue
        return preview_page(request, db, data, username, slug)
    take_click(db, background, request, data)
    return RedirectResponse(data["url"], status_code=302)
