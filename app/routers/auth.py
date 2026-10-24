import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..cache import rate_limit
from ..config import settings
from ..database import get_db
from ..deps import client_ip, get_current_user
from ..i18n import SIGNUP_EMAIL_BODY, SIGNUP_EMAIL_SUBJECT, get_lang, translate
from ..mailer import email_enabled, send_email
from ..models import PendingSignup, User, UsernameAlias, as_utc, utcnow
from ..otp import (
    CODE_LIFETIME,
    MAX_CODE_ATTEMPTS,
    RESEND_AFTER_SECONDS,
    codes_match,
    hash_code,
    new_code,
)
from ..profile import AVATARS, THEMES
from ..security import hash_password, verify_password
from ..templating import flash, render
from ..utils import validate_email, validate_password, validate_username
from .language import set_language_cookie

router = APIRouter()


def signup_code_hash(email: str, code: str) -> str:
    return hash_code("signup", email, code)


def is_taken(db: Session, username: str, email: str) -> bool:
    """Is this username or email already used by an account (or an old username of one)?"""
    taken = db.scalar(select(User.id).where(or_(User.username == username, User.email == email)))
    return bool(taken or db.get(UsernameAlias, username))


def create_user(db: Session, request: Request, username: str, email: str, password_hash: str,
                language: str, verified: bool) -> User | None:
    """Create the account. Returns None if someone grabbed the username or email a moment ago."""
    cookie_theme = request.cookies.get("theme")
    user = User(
        username=username,
        email=email,
        password_hash=password_hash,
        last_login_at=utcnow(),
        avatar=secrets.choice(AVATARS),
        theme=cookie_theme if cookie_theme in THEMES else "system",
        language=language,
        email_verified_at=utcnow() if verified else None,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None
    return user


def welcome(request: Request, user: User) -> RedirectResponse:
    request.session.pop("signup_email", None)
    request.session["user_id"] = user.id
    flash(request, "Account created. Welcome to Link Shortener!", "success")
    response = RedirectResponse("/dashboard", status_code=303)
    set_language_cookie(response, user.language)
    return response


def cooldown_left(pending: PendingSignup) -> int:
    waited = (utcnow() - as_utc(pending.sent_at)).total_seconds()
    return max(0, int(RESEND_AFTER_SECONDS - waited))


def send_signup_code(db: Session, username: str, email: str, password_hash: str,
                     lang: str) -> tuple[str, int] | None:
    """Email a fresh code and remember the pending sign-up. Returns (error, status) or None."""
    now = utcnow()
    # Tidy away abandoned sign-ups. Done fully inside the database: comparing dates in Python
    # would fail on databases (like SQLite) that hand back dates without a timezone.
    db.execute(
        delete(PendingSignup)
        .where(PendingSignup.expires_at < now - timedelta(days=1))
        .execution_options(synchronize_session=False)
    )
    pending = db.get(PendingSignup, email)
    if pending:
        wait = cooldown_left(pending)
        if wait:
            wait_text = "Please wait {seconds} seconds before asking for another code."
            return translate(lang, wait_text, seconds=wait), 429
    if not rate_limit(f"rl:signupcode:{email}", 5, 3600, local_fallback=True):
        return translate(lang, "Too many codes were requested for this email. "
                               "Try again in an hour."), 429
    if not rate_limit(f"rl:signupday:{now:%Y%m%d}", settings.signup_code_daily_limit, 86400,
                      local_fallback=True):
        return translate(lang, "Sign-ups are very busy right now. Please try again later."), 429

    code = new_code()
    if pending is None:
        pending = PendingSignup(email=email)
        db.add(pending)
    pending.username = username
    pending.password_hash = password_hash
    pending.language = lang
    pending.code_hash = signup_code_hash(email, code)
    pending.expires_at = now + CODE_LIFETIME
    pending.sent_at = now
    pending.attempts = 0
    db.commit()
    if not send_email(email, translate(lang, SIGNUP_EMAIL_SUBJECT),
                      translate(lang, SIGNUP_EMAIL_BODY, code=code)):
        db.delete(pending)
        db.commit()
        return translate(lang, "We could not send the email. Please try again later."), 503
    return None


def current_pending(request: Request, db: Session) -> PendingSignup | None:
    """The sign-up this browser is waiting on, or None (expired ones are removed)."""
    email = request.session.get("signup_email")
    pending = db.get(PendingSignup, email) if email else None
    if pending and as_utc(pending.expires_at) <= utcnow():
        db.delete(pending)
        db.commit()
        return None
    return pending


def start_over(request: Request, message: str) -> RedirectResponse:
    request.session.pop("signup_email", None)
    flash(request, message, "error")
    return RedirectResponse("/register", status_code=303)


@router.get("/")
def index(request: Request, user: User | None = Depends(get_current_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return render(request, "index.html")


@router.get("/register")
def register_page(request: Request, user: User | None = Depends(get_current_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return render(request, "register.html")


@router.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if not rate_limit(f"rl:register:{client_ip(request)}", 10, 3600):
        return render(request, "register.html", status_code=429,
                      error="Too many attempts. Try again later.")
    try:
        username = validate_username(username)
        email = validate_email(email)
        validate_password(password)
    except ValueError as e:
        return render(request, "register.html", status_code=400,
                      error=str(e), form={"username": username, "email": email})

    form = {"username": username, "email": email}
    if is_taken(db, username, email):
        return render(request, "register.html", status_code=400,
                      error="That username or email is already registered.", form=form)

    lang = get_lang(request)
    password_hash = hash_password(password)
    if not email_enabled():  # no way to send a code, so sign-up works without the check
        user = create_user(db, request, username, email, password_hash, lang, verified=False)
        if user is None:
            return render(request, "register.html", status_code=400,
                          error="That username or email is already registered.", form=form)
        return welcome(request, user)

    problem = send_signup_code(db, username, email, password_hash, lang)
    if problem:
        message, status = problem
        return render(request, "register.html", status_code=status, error=message, form=form)
    request.session["signup_email"] = email
    flash(request, "We sent a 6-digit code to {email}.", "success", email=email)
    return RedirectResponse("/register/verify", status_code=303)


@router.get("/register/verify")
def signup_verify_page(request: Request, db: Session = Depends(get_db)):
    pending = current_pending(request, db)
    if pending is None:
        return start_over(request, "That sign-up has expired. Please start again.")
    return render(request, "verify_signup.html", pending=pending)


@router.post("/register/verify")
def signup_verify(request: Request, code: str = Form(...), db: Session = Depends(get_db)):
    if not rate_limit(f"rl:signupverify:{client_ip(request)}", 30, 600):
        return render(request, "register.html", status_code=429,
                      error="Too many attempts. Try again later.")
    pending = current_pending(request, db)
    if pending is None:
        return start_over(request, "That sign-up has expired. Please start again.")

    if not codes_match(pending.code_hash, signup_code_hash(pending.email, code.strip())):
        pending.attempts += 1
        too_many = pending.attempts >= MAX_CODE_ATTEMPTS
        if too_many:
            db.delete(pending)
        db.commit()
        if too_many:
            return start_over(request, "Too many wrong codes. Please start again.")
        return render(request, "verify_signup.html", status_code=400, pending=pending,
                      error="That code is not correct.")

    username, email = pending.username, pending.email
    password_hash, language = pending.password_hash, pending.language
    db.delete(pending)
    db.commit()
    if is_taken(db, username, email):
        return start_over(request, "That username or email was just taken. Please start again.")
    user = create_user(db, request, username, email, password_hash, language, verified=True)
    if user is None:
        return start_over(request, "That username or email was just taken. Please start again.")
    return welcome(request, user)


@router.post("/register/resend")
def signup_resend(request: Request, db: Session = Depends(get_db)):
    pending = current_pending(request, db)
    if pending is None:
        return start_over(request, "That sign-up has expired. Please start again.")
    problem = send_signup_code(db, pending.username, pending.email, pending.password_hash,
                               get_lang(request))
    if problem:
        flash(request, problem[0], "error")
    else:
        flash(request, "We sent a new code.", "success")
    return RedirectResponse("/register/verify", status_code=303)


@router.post("/register/cancel")
def signup_cancel(request: Request, db: Session = Depends(get_db)):
    pending = current_pending(request, db)
    if pending is not None:
        db.delete(pending)
        db.commit()
    request.session.pop("signup_email", None)
    return RedirectResponse("/register", status_code=303)


@router.get("/login")
def login_page(request: Request, user: User | None = Depends(get_current_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return render(request, "login.html")


@router.post("/login")
def login(
    request: Request,
    identifier: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if not rate_limit(f"rl:login:{client_ip(request)}", 10, 300):
        return render(request, "login.html", status_code=429,
                      error="Too many attempts. Wait a few minutes.")
    ident = identifier.strip().lower()
    user = db.scalar(select(User).where(or_(User.username == ident, User.email == ident)))
    if not user or not verify_password(password, user.password_hash):
        return render(request, "login.html", status_code=400,
                      error="Wrong username/email or password.", form={"identifier": identifier})
    user.last_login_at = utcnow()
    db.commit()
    request.session.clear()
    request.session["user_id"] = user.id
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie("theme", user.theme, max_age=365 * 24 * 3600, httponly=True,
                        samesite="lax", secure=settings.https_only)
    set_language_cookie(response, user.language)  # their saved language follows them
    return response


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
