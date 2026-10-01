import json
import logging
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from ..cache import cache_get, cache_set
from ..config import settings
from ..database import get_db
from ..models import Click, Link, User, as_utc, utcnow
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


@router.get("/{username}/{slug}")
def follow(
    username: str,
    slug: str,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    username = username.lower()
    key = cache_key(username, slug)

    raw = cache_get(key)
    if raw:
        data = json.loads(raw)  # cache hit: no database query at all
    else:
        link = db.scalar(
            select(Link).join(User).where(User.username == username, Link.slug == slug)
        )
        if not link:
            raise HTTPException(404, "This short link does not exist.")
        expires = as_utc(link.expires_at) if link.expires_at else None
        data = {"id": link.id, "url": link.original_url,
                "exp": expires.isoformat() if expires else None}
        ttl = settings.cache_ttl
        if expires:
            ttl = max(1, min(ttl, int((expires - utcnow()).total_seconds())))
        cache_set(key, json.dumps(data), ttl)

    if data["exp"] and datetime.fromisoformat(data["exp"]) <= utcnow():
        raise HTTPException(410, "This short link has expired.")

    background.add_task(
        record_click,
        request.app.state.session_factory,
        data["id"],
        request.headers.get("user-agent"),
        request.headers.get("referer"),
    )
    return RedirectResponse(data["url"], status_code=302)
