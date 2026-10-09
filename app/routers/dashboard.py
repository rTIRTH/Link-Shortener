import csv
import io
import zipfile
from collections import Counter
from datetime import datetime, time, timedelta, timezone

import qrcode
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..cache import cache_delete, rate_limit
from ..config import settings
from ..database import get_db
from ..deps import require_user
from ..models import Click, Link, User, UsernameAlias, as_utc, utcnow
from ..security import hash_password
from ..templating import flash, render
from ..utils import (
    csv_safe,
    generate_slug,
    parse_moment,
    validate_link_password,
    validate_slug,
    validate_url,
)

router = APIRouter(prefix="/dashboard")


def cache_key(username: str, slug: str) -> str:
    return f"link:{username}:{slug}"


def forget_link(db: Session, user: User, slug: str) -> None:
    """Remove a link from the Redis cache under the current AND previous usernames."""
    old = db.scalars(select(UsernameAlias.username).where(UsernameAlias.user_id == user.id))
    for name in [user.username, *old]:
        cache_delete(cache_key(name, slug))


def link_status(link: Link, now: datetime | None = None) -> str:
    """'expired', 'scheduled' (not started yet) or 'active'."""
    now = now or utcnow()
    if link.expires_at and as_utc(link.expires_at) <= now:
        return "expired"
    if link.starts_at and as_utc(link.starts_at) > now:
        return "scheduled"
    return "active"


def read_schedule(starts_at: str, starts_at_utc: str, expires_at: str, expires_at_utc: str):
    """Parse the start/end form fields. Raises ValueError with a friendly message."""
    start = parse_moment(starts_at_utc, starts_at)
    end = parse_moment(expires_at_utc, expires_at, end_of_day=True)
    if start and end and start >= end:
        raise ValueError("The end time must be after the start time.")
    return start, end


def read_settings(
    link: Link, starts_at: str, starts_at_utc: str, expires_at: str, expires_at_utc: str,
    password_action: str, new_password: str,
):
    """Schedule + password choice from a form -> (start, end, new_password_hash)."""
    start, end = read_schedule(starts_at, starts_at_utc, expires_at, expires_at_utc)
    if password_action == "set":
        new_hash = hash_password(validate_link_password(new_password))
    elif password_action == "remove":
        new_hash = None
    elif password_action == "keep":
        new_hash = link.password_hash
    else:
        raise ValueError("Unknown password option.")
    return start, end, new_hash


def short_url(request: Request, user: User, link: Link) -> str:
    base = settings.base_url or str(request.base_url).rstrip("/")
    return f"{base}/{user.username}/{link.slug}"


def user_links(db: Session, user: User, ids: list[int] | None = None) -> list[Link]:
    stmt = select(Link).where(Link.user_id == user.id).order_by(Link.created_at.desc())
    if ids:
        stmt = stmt.where(Link.id.in_(ids))
    return list(db.scalars(stmt))


def qr_png_bytes(text: str) -> bytes:
    buf = io.BytesIO()
    qrcode.make(text).save(buf, format="PNG")
    return buf.getvalue()


@router.get("")
def dashboard(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    links = user_links(db, user)
    rows = [
        {
            "link": link,
            "short_url": short_url(request, user, link),
            "status": link_status(link),
            "locked": bool(link.password_hash),
        }
        for link in links
    ]
    total_clicks = sum(link.click_count for link in links)
    return render(request, "dashboard.html", user, rows=rows, total_clicks=total_clicks)


@router.post("/links")
def create_link(
    request: Request,
    original_url: str = Form(...),
    slug: str = Form(""),
    starts_at: str = Form(""),
    starts_at_utc: str = Form(""),
    expires_at: str = Form(""),
    expires_at_utc: str = Form(""),
    link_password: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    def back(message: str, **params):
        flash(request, message, "error", **params)
        return RedirectResponse("/dashboard", status_code=303)

    if not rate_limit(f"rl:create:{user.id}", 30, 60):
        return back("You're creating links too quickly. Wait a minute.")
    try:
        url = validate_url(original_url, blocked_hosts=(request.url.hostname or "",))
    except ValueError as e:
        return back(str(e))

    try:
        start, end = read_schedule(starts_at, starts_at_utc, expires_at, expires_at_utc)
        if end and end <= utcnow():
            raise ValueError("The end time must be in the future.")
        pw_hash = hash_password(validate_link_password(link_password)) if link_password else None
    except ValueError as e:
        return back(str(e))

    custom = slug.strip()
    if custom:
        try:
            slug_value = validate_slug(custom)
        except ValueError as e:
            return back(str(e))
        taken = db.scalar(select(Link.id).where(Link.user_id == user.id, Link.slug == slug_value))
        if taken:
            return back("You already have a link called '{slug}'.", slug=slug_value)
    else:
        for _ in range(10):  # retry on the (very unlikely) collision
            slug_value = generate_slug()
            exists = db.scalar(
                select(Link.id).where(Link.user_id == user.id, Link.slug == slug_value)
            )
            if not exists:
                break
        else:
            return back("Could not generate a unique code. Try again.")

    link = Link(
        user_id=user.id,
        slug=slug_value,
        original_url=url,
        starts_at=start,
        expires_at=end,
        password_hash=pw_hash,
    )
    db.add(link)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return back("That alias was just taken. Try another.")
    flash(request, "Created {url}", "success", url=short_url(request, user, link))
    return RedirectResponse("/dashboard", status_code=303)


@router.post("/links/bulk-delete")
def bulk_delete(
    request: Request,
    ids: list[int] = Form(default=[]),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    if not ids:
        flash(request, "Select at least one link first.", "error")
        return RedirectResponse("/dashboard", status_code=303)
    links = user_links(db, user, ids)  # only the user's own links can match
    for link in links:
        forget_link(db, user, link.slug)
        db.delete(link)
    db.commit()
    flash(request, "Deleted {n} link(s).", "success", n=len(links))
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/links/export.csv")
def export_csv(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "short_url", "slug", "original_url", "clicks", "created_at",
        "starts_at", "expires_at", "password_protected",
    ])
    for link in user_links(db, user):
        writer.writerow([
            short_url(request, user, link),
            csv_safe(link.slug),
            csv_safe(link.original_url),
            link.click_count,
            as_utc(link.created_at).isoformat(),
            as_utc(link.starts_at).isoformat() if link.starts_at else "",
            as_utc(link.expires_at).isoformat() if link.expires_at else "",
            "yes" if link.password_hash else "no",
        ])
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="link-shortener-links.csv"'},
    )


@router.get("/links/qr.zip")
def qr_zip(
    request: Request,
    ids: list[int] = Query(default=[]),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    links = user_links(db, user, ids or None)  # no ids = all links
    if not links:
        raise HTTPException(404, "No links to download.")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for link in links:
            zf.writestr(f"{link.slug}.png", qr_png_bytes(short_url(request, user, link)))
    return Response(
        buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="link-shortener-qr-codes.zip"'},
    )


def get_owned_link(db: Session, user: User, link_id: int) -> Link:
    link = db.scalar(select(Link).where(Link.id == link_id, Link.user_id == user.id))
    if not link:
        raise HTTPException(404, "Link not found.")
    return link


@router.get("/links/{link_id}/qr.png")
def qr_single(
    request: Request, link_id: int, download: bool = Query(False),
    user: User = Depends(require_user), db: Session = Depends(get_db),
):
    link = get_owned_link(db, user, link_id)
    headers = {}
    if download:  # the dashboard button: save the file instead of showing it
        headers["Content-Disposition"] = f'attachment; filename="{link.slug}-qr.png"'
    return Response(
        qr_png_bytes(short_url(request, user, link)), media_type="image/png", headers=headers
    )


@router.get("/links/{link_id}")
def link_detail(
    request: Request, link_id: int,
    user: User = Depends(require_user), db: Session = Depends(get_db),
):
    link = get_owned_link(db, user, link_id)
    today = utcnow().date()
    since = datetime.combine(today - timedelta(days=13), time.min, tzinfo=timezone.utc)
    clicks = list(
        db.scalars(select(Click).where(Click.link_id == link.id, Click.clicked_at >= since))
    )

    per_day = Counter(as_utc(c.clicked_at).date() for c in clicks)
    days = [today - timedelta(days=i) for i in range(13, -1, -1)]
    series = [{"label": d.strftime("%d %b"), "count": per_day.get(d, 0)} for d in days]
    peak = max((s["count"] for s in series), default=0) or 1
    for s in series:
        s["pct"] = round(s["count"] / peak * 100)

    return render(
        request, "link_detail.html", user,
        link=link,
        short_url=short_url(request, user, link),
        status=link_status(link),
        series=series,
        recent_total=len(clicks),
        devices=Counter(c.device for c in clicks).most_common(),
        referrers=Counter(c.referrer or "Direct" for c in clicks).most_common(5),
    )


@router.post("/links/{link_id}/delete")
def delete_one(
    request: Request, link_id: int,
    user: User = Depends(require_user), db: Session = Depends(get_db),
):
    link = get_owned_link(db, user, link_id)
    forget_link(db, user, link.slug)
    db.delete(link)
    db.commit()
    flash(request, "Link deleted.", "success")
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/links/{link_id}/edit")
def edit_page(
    request: Request, link_id: int,
    user: User = Depends(require_user), db: Session = Depends(get_db),
):
    link = get_owned_link(db, user, link_id)
    return render(
        request, "edit_link.html", user,
        link=link, short_url=short_url(request, user, link), status=link_status(link),
    )


@router.post("/links/{link_id}/edit")
def edit_save(
    request: Request,
    link_id: int,
    original_url: str = Form(...),
    starts_at: str = Form(""),
    starts_at_utc: str = Form(""),
    expires_at: str = Form(""),
    expires_at_utc: str = Form(""),
    password_action: str = Form("keep"),
    new_password: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    link = get_owned_link(db, user, link_id)
    edit_url = f"/dashboard/links/{link.id}/edit"

    def back(message: str):
        flash(request, message, "error")
        return RedirectResponse(edit_url, status_code=303)

    try:
        url = validate_url(original_url, blocked_hosts=(request.url.hostname or "",))
        start, end, new_hash = read_settings(
            link, starts_at, starts_at_utc, expires_at, expires_at_utc,
            password_action, new_password,
        )
    except ValueError as e:
        return back(str(e))

    link.original_url = url
    link.starts_at = start
    link.expires_at = end
    link.password_hash = new_hash
    db.commit()
    forget_link(db, user, link.slug)  # visitors must see the new settings straight away
    flash(request, "Link updated.", "success")
    return RedirectResponse("/dashboard", status_code=303)
