"""Email alerts for a link's owner.

Three things can be switched on for each link (the Link.alert_* columns):

  * "limit":  the link has used its last click,
  * "clicks": the link has reached the number of clicks the owner chose,
  * "expiry": the link will end within a day.

Each alert is sent once. Its "sent" time is claimed with one atomic UPDATE before the email goes
out, so two clicks at the same moment (or two server workers) can never send it twice. Changing
the setting arms it again. If the email cannot be sent, the claim is given back so that a later
click or sweep tries again.

Clicks are checked in the background task that already records them, so visitors never wait.
Links that are about to end have no click to hang on to, so a "sweep" looks for them (and for
any limit or milestone email that could not be sent the first time): after clicks and dashboard
visits (at most every ten minutes), and whenever /run-alerts is opened.
"""
import logging
from datetime import timedelta

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from .cache import rate_limit
from .config import settings
from .i18n import (
    ALERT_CLICKS_BODY,
    ALERT_CLICKS_SUBJECT,
    ALERT_EXPIRY_BODY,
    ALERT_EXPIRY_SUBJECT,
    ALERT_LIMIT_BODY,
    ALERT_LIMIT_SUBJECT,
    ascii_digits,
    format_date,
    native_digits,
    translate,
)
from .mailer import email_enabled, send_email
from .models import Link, User, as_utc, utcnow
from .resettoken import configured_site_url
from .utils import MAX_CLICK_LIMIT

log = logging.getLogger("linkshortener.alerts")

EXPIRY_NOTICE = timedelta(hours=24)  # "about to end" means: within this long
SWEEP_EVERY_SECONDS = 600
SWEEP_BATCH = 100

_SENT = {  # which column remembers that an alert went out
    "limit": "alert_limit_sent_at",
    "clicks": "alert_clicks_sent_at",
    "expiry": "alert_expiry_sent_at",
}


# ---------- what the owner types ----------

def parse_alert_clicks(raw: str | None) -> int | None:
    """The 'tell me at this many clicks' box -> a whole number, or None. Hindi digits work."""
    text = ascii_digits((raw or "").strip()).replace(",", "")
    if not text:
        return None
    if not text.isascii() or not text.isdigit() or not 1 <= int(text) <= MAX_CLICK_LIMIT:
        raise ValueError("The number of clicks must be a whole number from 1 to 1,000,000.")
    return int(text)


def read_alert_settings(
    on_limit: bool, on_expiry: bool, clicks_raw: str | None, *, limit: int | None, end,
    used: int, old_clicks: int | None = None,
) -> tuple[bool, bool, int | None]:
    """Check the three alert choices against the link they belong to. Raises ValueError."""
    clicks = parse_alert_clicks(clicks_raw)
    if on_limit and limit is None:
        raise ValueError("Set a click limit first, then you can be told when it is reached.")
    if on_expiry and end is None:
        raise ValueError("Set an end time first, then you can be told before it ends.")
    if clicks is not None and clicks != old_clicks and clicks <= used:
        raise ValueError("Choose a number higher than the clicks this link already has.")
    return on_limit, on_expiry, clicks


def _moment(value):
    return as_utc(value) if value else None


def apply_alert_settings(
    link: Link, on_limit: bool, on_expiry: bool, clicks: int | None, *,
    limit_changed: bool = False, end_changed: bool = False,
) -> None:
    """Store the choices. Whatever changed is armed again, so it can be sent once more."""
    if on_limit != link.alert_limit or limit_changed:
        link.alert_limit_sent_at = None
    if on_expiry != link.alert_expiry or end_changed:
        link.alert_expiry_sent_at = None
    if clicks != link.alert_clicks:
        link.alert_clicks_sent_at = None
    link.alert_limit, link.alert_expiry, link.alert_clicks = on_limit, on_expiry, clicks


def same_moment(a, b) -> bool:
    return _moment(a) == _moment(b)


# ---------- sending ----------

def _claim(db: Session, link_id: int, kind: str) -> bool:
    """Mark the alert as sent. True only for the one caller that gets there first."""
    column = getattr(Link, _SENT[kind])
    done = db.execute(
        update(Link).where(Link.id == link_id, column.is_(None))
        .values({_SENT[kind]: utcnow()}).execution_options(synchronize_session=False)
    )
    db.commit()
    return done.rowcount == 1


def _release(db: Session, link_id: int, kind: str) -> None:
    db.execute(
        update(Link).where(Link.id == link_id)
        .values({_SENT[kind]: None}).execution_options(synchronize_session=False)
    )
    db.commit()


def _within_daily_caps(user_id: int) -> bool:
    """A cap per person and one for the whole site (all emails share one provider quota)."""
    day = f"{utcnow():%Y%m%d}"
    return (
        rate_limit(f"rl:alertuser:{user_id}:{day}", settings.alert_user_daily_limit, 86400,
                   local_fallback=True)
        and rate_limit(f"rl:alertday:{day}", settings.alert_email_daily_limit, 86400,
                       local_fallback=True)
    )


def _message(kind: str, lang: str, link: Link, owner: User, site: str) -> tuple[str, str]:
    root = configured_site_url() or site  # never built from a visitor's Host header
    words = {
        "name": f"{owner.username}/{link.slug}",
        "link": f"{root}/{owner.username}/{link.slug}",
        "edit": f"{root}/dashboard/links/{link.id}/edit",
        "stats": f"{root}/dashboard/links/{link.id}",
    }
    if kind == "limit":
        words["limit"] = link.click_limit
        return (translate(lang, ALERT_LIMIT_SUBJECT, **words),
                translate(lang, ALERT_LIMIT_BODY, **words))
    if kind == "clicks":
        words["count"] = link.alert_clicks
        return (translate(lang, ALERT_CLICKS_SUBJECT, **words),
                translate(lang, ALERT_CLICKS_BODY, **words))
    end = as_utc(link.expires_at)
    clock = native_digits(lang, end.strftime("%H:%M"))
    words["when"] = f"{format_date(end, lang, year=True)} {clock} UTC"
    return (translate(lang, ALERT_EXPIRY_SUBJECT, **words),
            translate(lang, ALERT_EXPIRY_BODY, **words))


def deliver(db: Session, link: Link, owner: User, kind: str, site: str = "") -> bool:
    """Claim the alert, then email it. True if the email went out."""
    if not _claim(db, link.id, kind):
        return False  # somebody else already did
    sent = False
    if _within_daily_caps(owner.id):
        subject, body = _message(kind, owner.language, link, owner, site)
        sent = send_email(owner.email, subject, body)
    if not sent:
        _release(db, link.id, kind)  # try again at the next click or sweep
    return sent


# ---------- when to look ----------

def send_due(db: Session, link: Link, owner: User, site: str = "") -> int:
    """Send whatever is due for this link right now. Returns how many emails went out."""
    now = utcnow()
    used = link.click_count
    limit_due = bool(
        link.alert_limit and link.alert_limit_sent_at is None
        and link.click_limit is not None and used >= link.click_limit
    )
    clicks_due = bool(
        link.alert_clicks and link.alert_clicks_sent_at is None and used >= link.alert_clicks
    )
    end = _moment(link.expires_at)
    expiry_due = bool(
        link.alert_expiry and link.alert_expiry_sent_at is None and link.is_active
        and end and now < end <= now + EXPIRY_NOTICE
    )
    sent = 0
    if limit_due and clicks_due:
        _claim(db, link.id, "clicks")  # the limit email already says everything
    if limit_due:
        sent += deliver(db, link, owner, "limit", site)
    elif clicks_due:
        sent += deliver(db, link, owner, "clicks", site)
    if expiry_due:
        sent += deliver(db, link, owner, "expiry", site)
    return sent


def after_click(factory: sessionmaker, link_id: int, site: str = "") -> None:
    """Called once a click has been counted: did that click reach a limit or a milestone?"""
    if not email_enabled():
        return
    with factory() as db:
        armed = db.execute(
            select(Link.alert_limit, Link.alert_clicks).where(Link.id == link_id)
        ).first()
        if armed is None or not (armed.alert_limit or armed.alert_clicks):
            return  # the usual case: nothing to do, and nothing else was read
        link = db.get(Link, link_id)
        send_due(db, link, db.get(User, link.user_id), site)


def send_due_alerts(factory: sessionmaker, site: str = "") -> int:
    """Look at every link that has an alert waiting (links that end within a day, and limits or
    milestones whose email did not go out). Returns how many emails were sent."""
    if not email_enabled():
        return 0
    now = utcnow()
    sent = 0
    with factory() as db:
        waiting = list(db.scalars(
            select(Link.id).where(or_(
                and_(Link.alert_limit.is_(True), Link.alert_limit_sent_at.is_(None),
                     Link.click_limit.is_not(None), Link.click_count >= Link.click_limit),
                and_(Link.alert_clicks.is_not(None), Link.alert_clicks_sent_at.is_(None),
                     Link.click_count >= Link.alert_clicks),
                and_(Link.alert_expiry.is_(True), Link.alert_expiry_sent_at.is_(None),
                     Link.is_active.is_(True), Link.expires_at.is_not(None),
                     Link.expires_at > now, Link.expires_at <= now + EXPIRY_NOTICE),
            )).limit(SWEEP_BATCH)
        ))
        for link_id in waiting:
            link = db.get(Link, link_id)
            sent += send_due(db, link, db.get(User, link.user_id), site)
    return sent


def maybe_sweep(factory: sessionmaker, site: str = "") -> None:
    """send_due_alerts, but at most once every ten minutes however often it is asked."""
    if email_enabled() and rate_limit("alerts:sweep", 1, SWEEP_EVERY_SECONDS, local_fallback=True):
        try:
            send_due_alerts(factory, site)
        except Exception:  # an alert problem must never break the page or the redirect
            log.exception("Looking for waiting alerts failed")
