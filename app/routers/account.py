import hashlib
import hmac
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..cache import cache_delete, rate_limit
from ..config import settings
from ..database import get_db
from ..deps import require_user
from ..mailer import email_enabled, send_email
from ..models import Click, EmailChange, Link, User, UsernameAlias, as_utc, utcnow
from ..profile import AVATARS, MAX_OLD_USERNAMES, THEMES
from ..security import hash_password, verify_password
from ..templating import flash, render
from ..utils import validate_email, validate_password, validate_username
from .dashboard import cache_key

router = APIRouter(prefix="/account")

CODE_LIFETIME = timedelta(minutes=10)
RESEND_AFTER_SECONDS = 60
MAX_CODE_ATTEMPTS = 5


def back(request: Request, message: str, category: str = "error", anchor: str = ""):
    flash(request, message, category)
    return RedirectResponse(f"/account{anchor}", status_code=303)


def password_error(request: Request, user: User, password: str) -> str | None:
    """Sensitive actions re-ask for the password (and are rate limited)."""
    if not rate_limit(f"rl:account:{user.id}", 10, 300):
        return "Too many attempts. Wait a few minutes and try again."
    if not verify_password(password, user.password_hash):
        return "That password is not correct."
    return None


def code_hash(user_id: int, new_email: str, code: str) -> str:
    message = f"{user_id}:{new_email}:{code}".encode()
    return hmac.new(settings.secret_key.encode(), message, hashlib.sha256).hexdigest()


def live_pending(db: Session, user: User) -> EmailChange | None:
    """The user's pending email change, or None (expired ones are removed)."""
    pending = db.get(EmailChange, user.id)
    if pending and as_utc(pending.expires_at) <= utcnow():
        db.delete(pending)
        db.commit()
        return None
    return pending


@router.get("")
def account_page(request: Request, user: User = Depends(require_user),
                 db: Session = Depends(get_db)):
    return render(
        request, "account.html", user,
        avatars=AVATARS,
        email_ready=email_enabled(),
        pending=live_pending(db, user),
        old_usernames=[a.username for a in user.old_usernames],
        max_old=MAX_OLD_USERNAMES,
    )


# ---------- avatar and theme ----------

@router.post("/avatar")
def set_avatar(request: Request, avatar: str = Form(...), user: User = Depends(require_user),
               db: Session = Depends(get_db)):
    if avatar not in AVATARS:
        return back(request, "Please pick one of the avatars shown.", anchor="#profile")
    user.avatar = avatar
    db.commit()
    return back(request, "Avatar updated.", "success", "#profile")


@router.post("/theme")
def set_theme(request: Request, theme: str = Form(...), user: User = Depends(require_user),
              db: Session = Depends(get_db)):
    if theme not in THEMES:
        return back(request, "Unknown theme.", anchor="#appearance")
    user.theme = theme
    db.commit()
    response = back(request, "Appearance saved.", "success", "#appearance")
    response.set_cookie("theme", theme, max_age=365 * 24 * 3600, httponly=True,
                        samesite="lax", secure=settings.https_only)
    return response


# ---------- username ----------

@router.post("/username")
def change_username(request: Request, new_username: str = Form(...), password: str = Form(...),
                    user: User = Depends(require_user), db: Session = Depends(get_db)):
    error = password_error(request, user, password)
    if error:
        return back(request, error, anchor="#profile")
    try:
        new_name = validate_username(new_username)
    except ValueError as e:
        return back(request, str(e), anchor="#profile")
    if new_name == user.username:
        return back(request, "That is already your username.", anchor="#profile")

    alias = db.get(UsernameAlias, new_name)
    taken = db.scalar(select(User.id).where(User.username == new_name))
    if taken or (alias and alias.user_id != user.id):
        return back(request, "That username is taken.", anchor="#profile")

    if alias:  # taking back one of your own old names
        db.delete(alias)
    elif len(user.old_usernames) >= MAX_OLD_USERNAMES:
        return back(request, f"You have already used {MAX_OLD_USERNAMES} previous usernames, "
                             "which is the limit.", anchor="#profile")
    db.add(UsernameAlias(username=user.username, user_id=user.id))
    user.username = new_name
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return back(request, "That username was just taken. Try another.", anchor="#profile")
    return back(request, f"Username changed to {new_name}. Your old links still work.",
                "success", "#profile")


# ---------- password ----------

@router.post("/password")
def change_password(request: Request, current_password: str = Form(...),
                    new_password: str = Form(...), user: User = Depends(require_user),
                    db: Session = Depends(get_db)):
    error = password_error(request, user, current_password)
    if error:
        return back(request, error, anchor="#password")
    try:
        validate_password(new_password)
    except ValueError as e:
        return back(request, str(e), anchor="#password")
    user.password_hash = hash_password(new_password)
    db.commit()
    return back(request, "Password changed.", "success", "#password")


# ---------- email change with a one-time code ----------

def issue_code(db: Session, user: User, new_email: str) -> bool:
    """Create (or replace) the pending change and email the code. True if it was sent."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    pending = db.get(EmailChange, user.id)
    if pending is None:
        pending = EmailChange(user_id=user.id)
        db.add(pending)
    pending.new_email = new_email
    pending.code_hash = code_hash(user.id, new_email, code)
    pending.expires_at = utcnow() + CODE_LIFETIME
    pending.sent_at = utcnow()
    pending.attempts = 0
    db.commit()
    body = (f"Your Link Shortener verification code is {code}.\n\n"
            "It expires in 10 minutes. If you did not ask to change your email, "
            "you can ignore this message.")
    if send_email(new_email, "Your Link Shortener verification code", body):
        return True
    db.delete(pending)
    db.commit()
    return False


def cooldown_left(pending: EmailChange | None) -> int:
    if pending is None:
        return 0
    waited = (utcnow() - as_utc(pending.sent_at)).total_seconds()
    return max(0, int(RESEND_AFTER_SECONDS - waited))


@router.post("/email/request")
def email_request(request: Request, new_email: str = Form(...), password: str = Form(...),
                  user: User = Depends(require_user), db: Session = Depends(get_db)):
    if not email_enabled():
        return back(request, "Changing email is not available on this server yet.",
                    anchor="#email")
    error = password_error(request, user, password)
    if error:
        return back(request, error, anchor="#email")
    try:
        new_email = validate_email(new_email)
    except ValueError as e:
        return back(request, str(e), anchor="#email")
    if new_email == user.email:
        return back(request, "That is already your email.", anchor="#email")
    if db.scalar(select(User.id).where(User.email == new_email)):
        return back(request, "That email is already used by another account.", anchor="#email")

    wait = cooldown_left(live_pending(db, user))
    if wait:
        return back(request, f"Please wait {wait} seconds before asking for another code.",
                    anchor="#email")
    if not rate_limit(f"rl:emailcode:{user.id}", 5, 3600):
        return back(request, "Too many codes requested. Try again in an hour.", anchor="#email")
    if not issue_code(db, user, new_email):
        return back(request, "We could not send the email. Please try again later.",
                    anchor="#email")
    flash(request, f"We sent a 6-digit code to {new_email}.", "success")
    return RedirectResponse("/account/email/verify", status_code=303)


@router.get("/email/verify")
def verify_page(request: Request, user: User = Depends(require_user),
                db: Session = Depends(get_db)):
    pending = live_pending(db, user)
    if pending is None:
        return back(request, "There is no email change in progress.", anchor="#email")
    return render(request, "verify_email.html", user, pending=pending)


@router.post("/email/verify")
def verify_code(request: Request, code: str = Form(...), user: User = Depends(require_user),
                db: Session = Depends(get_db)):
    pending = live_pending(db, user)
    if pending is None:
        return back(request, "That code has expired. Please start again.", anchor="#email")

    expected = pending.code_hash
    given = code_hash(user.id, pending.new_email, code.strip())
    if not hmac.compare_digest(expected, given):
        pending.attempts += 1
        too_many = pending.attempts >= MAX_CODE_ATTEMPTS
        if too_many:
            db.delete(pending)
        db.commit()
        if too_many:
            return back(request, "Too many wrong codes. Please start again.", anchor="#email")
        return render(request, "verify_email.html", user, pending=pending, status_code=400,
                      error="That code is not correct.")

    if db.scalar(select(User.id).where(User.email == pending.new_email, User.id != user.id)):
        db.delete(pending)
        db.commit()
        return back(request, "That email was just taken by another account.", anchor="#email")
    user.email = pending.new_email
    db.delete(pending)
    db.commit()
    return back(request, f"Email changed to {user.email}.", "success", "#email")


@router.post("/email/resend")
def email_resend(request: Request, user: User = Depends(require_user),
                 db: Session = Depends(get_db)):
    pending = live_pending(db, user)
    if pending is None:
        return back(request, "There is no email change in progress.", anchor="#email")
    wait = cooldown_left(pending)
    if wait:
        flash(request, f"Please wait {wait} seconds before asking for another code.", "error")
        return RedirectResponse("/account/email/verify", status_code=303)
    if not rate_limit(f"rl:emailcode:{user.id}", 5, 3600):
        return back(request, "Too many codes requested. Try again in an hour.", anchor="#email")
    if not issue_code(db, user, pending.new_email):
        return back(request, "We could not send the email. Please try again later.",
                    anchor="#email")
    flash(request, "We sent a new code.", "success")
    return RedirectResponse("/account/email/verify", status_code=303)


@router.post("/email/cancel")
def email_cancel(request: Request, user: User = Depends(require_user),
                 db: Session = Depends(get_db)):
    pending = db.get(EmailChange, user.id)
    if pending:
        db.delete(pending)
        db.commit()
    return back(request, "Email change cancelled.", "success", "#email")


# ---------- delete account ----------

@router.post("/delete")
def delete_account(request: Request, password: str = Form(...), confirm: str = Form(""),
                   user: User = Depends(require_user), db: Session = Depends(get_db)):
    if confirm.strip().lower() != user.username:
        return back(request, "Type your username exactly to confirm.", anchor="#danger")
    error = password_error(request, user, password)
    if error:
        return back(request, error, anchor="#danger")

    names = [user.username, *(a.username for a in user.old_usernames)]
    for link in user.links:
        for name in names:
            cache_delete(cache_key(name, link.slug))
    own_links = select(Link.id).where(Link.user_id == user.id)
    db.execute(delete(Click).where(Click.link_id.in_(own_links)))
    db.delete(user)
    db.commit()

    request.session.clear()
    flash(request, "Your account and all its links were deleted.", "success")
    return RedirectResponse("/", status_code=303)
