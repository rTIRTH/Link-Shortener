import csv
import io
import zipfile
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone

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
from ..templating import flash, render
from ..utils import csv_safe, generate_slug, validate_slug, validate_url

router = APIRouter(prefix="/dashboard")


def cache_key(username: str, slug: str) -> str:
    return f"link:{username}:{slug}"


def forget_link(db: Session, user: User, slug: str) -> None:
    """Remove a link from the Redis cache under the current AND previous usernames."""
    old = db.scalars(select(UsernameAlias.username).where(UsernameAlias.user_id == user.id))
    for name in [user.username, *old]:
        cache_delete(cache_key(name, slug))


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
            "expired": bool(link.expires_at and as_utc(link.expires_at) <= utcnow()),
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
    expires_on: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    def back(message: str):
        flash(request, message, "error")
        return RedirectResponse("/dashboard", status_code=303)

    if not rate_limit(f"rl:create:{user.id}", 30, 60):
        return back("You're creating links too quickly. Wait a minute.")
    try:
        url = validate_url(original_url, blocked_hosts=(request.url.hostname or "",))
    except ValueError as e:
        return back(str(e))

    expires_at = None
    if expires_on.strip():
        try:
            day = date.fromisoformat(expires_on.strip())
        except ValueError:
            return back("Expiry date is not valid.")
        expires_at = datetime.combine(day, time(23, 59, 59), tzinfo=timezone.utc)
        if expires_at <= utcnow():
            return back("Expiry date must be in the future.")

    custom = slug.strip()
    if custom:
        try:
            slug_value = validate_slug(custom)
        except ValueError as e:
            return back(str(e))
        taken = db.scalar(select(Link.id).where(Link.user_id == user.id, Link.slug == slug_value))
        if taken:
            return back(f"You already have a link called '{slug_value}'.")
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

    link = Link(user_id=user.id, slug=slug_value, original_url=url, expires_at=expires_at)
    db.add(link)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return back("That alias was just taken. Try another.")
    flash(request, f"Created {short_url(request, user, link)}", "success")
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
    flash(request, f"Deleted {len(links)} link(s).", "success")
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/links/export.csv")
def export_csv(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["short_url", "slug", "original_url", "clicks", "created_at", "expires_at"])
    for link in user_links(db, user):
        writer.writerow([
            short_url(request, user, link),
            csv_safe(link.slug),
            csv_safe(link.original_url),
            link.click_count,
            as_utc(link.created_at).isoformat(),
            as_utc(link.expires_at).isoformat() if link.expires_at else "",
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
    request: Request, link_id: int,
    user: User = Depends(require_user), db: Session = Depends(get_db),
):
    link = get_owned_link(db, user, link_id)
    return Response(qr_png_bytes(short_url(request, user, link)), media_type="image/png")


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
