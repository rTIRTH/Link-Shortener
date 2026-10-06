import json
import logging
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from ..cache import cache_get, cache_set, rate_limit
from ..config import settings
from ..database import get_db
from ..deps import client_ip
from ..models import Click, Link, User, UsernameAlias, as_utc, utcnow
from ..security import verify_password
from ..templating import render
from ..utils import parse_device
from .dashboard import cache_key

router = APIRouter()
log = logging.getLogger("linkshortener")


def record_click(factory: sessionmaker, link_id: int, user_agent: str | None, referrer: str | None):
    """Runs AFTER the redirect is sent, so analytics never slow the visitor down."""
    try:
        with factory() as db:
            host = None
            if referrer:
                host = urlparse(referrer).netloc[:255] or None
            db.add(Click(link_id=link_id, device=parse_device(user_agent), referrer=host))
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
    }
    ttl = settings.cache_ttl
    if expires:
        ttl = max(1, min(ttl, int((expires - utcnow()).total_seconds())))
    cache_set(key, json.dumps(data), ttl)
    return data


def check_window(data: dict) -> None:
    """Raise if the link has expired or has not started yet."""
    now = utcnow()
    if data.get("exp") and datetime.fromisoformat(data["exp"]) <= now:
        raise HTTPException(410, "This short link has expired.")
    if data.get("start") and datetime.fromisoformat(data["start"]) > now:
        raise HTTPException(403, "This short link is not active yet. Please check back later.")


def count_click(background: BackgroundTasks, request: Request, link_id: int) -> None:
    background.add_task(
        record_click,
        request.app.state.session_factory,
        link_id,
        request.headers.get("user-agent"),
        request.headers.get("referer"),
    )


def viewer(request: Request, db: Session) -> User | None:
    """The logged-in user (only looked up when we render a page, never on plain redirects)."""
    user_id = request.session.get("user_id")
    return db.get(User, user_id) if user_id else None


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
        return render(request, "unlock.html", viewer(request, db), username=username, slug=slug)
    count_click(background, request, data["id"])
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

    count_click(background, request, data["id"])
    return RedirectResponse(data["url"], status_code=302)
