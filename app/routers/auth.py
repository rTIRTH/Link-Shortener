from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..cache import rate_limit
from ..database import get_db
from ..deps import client_ip, get_current_user
from ..models import User, utcnow
from ..security import hash_password, verify_password
from ..templating import flash, render
from ..utils import validate_email, validate_password, validate_username

router = APIRouter()


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

    exists = db.scalar(select(User).where(or_(User.username == username, User.email == email)))
    if exists:
        return render(request, "register.html", status_code=400,
                      error="That username or email is already registered.",
                      form={"username": username, "email": email})

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        last_login_at=utcnow(),
    )
    db.add(user)
    db.commit()
    request.session["user_id"] = user.id
    flash(request, "Account created. Welcome to Link Shortener!", "success")
    return RedirectResponse("/dashboard", status_code=303)


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
    return RedirectResponse("/dashboard", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
