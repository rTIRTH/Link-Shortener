from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..models import Click, Link, User, utcnow
from ..templating import render

router = APIRouter(prefix="/admin")


@router.get("")
def admin_home(
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    week_ago = utcnow() - timedelta(days=7)
    stats = {
        "users": db.scalar(select(func.count(User.id))),
        "active_7d": db.scalar(
            select(func.count(User.id)).where(User.last_login_at >= week_ago)
        ),
        "links": db.scalar(select(func.count(Link.id))),
        "clicks": db.scalar(select(func.count(Click.id))),
    }
    users = db.execute(
        select(User, func.count(Link.id))
        .outerjoin(Link, Link.user_id == User.id)
        .group_by(User.id)
        .order_by(User.created_at.desc())
        .limit(100)
    ).all()
    top_links = db.execute(
        select(Link, User.username)
        .join(User, User.id == Link.user_id)
        .order_by(Link.click_count.desc())
        .limit(10)
    ).all()
    return render(request, "admin.html", user, stats=stats, users=users, top_links=top_links)
