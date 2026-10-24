"""Email code at sign-up: the account only exists after the emailed code is entered."""
import re
from datetime import timedelta
from pathlib import Path

import pytest

from app.config import settings
from app.models import PendingSignup, User, utcnow

PW = "password123"


@pytest.fixture()
def outbox(monkeypatch):
    """Switch email on, and collect what would have been sent: (to, subject, body)."""
    sent = []
    monkeypatch.setattr(settings, "email_backend", "console")
    monkeypatch.setattr("app.routers.auth.send_email",
                        lambda to, subject, body: sent.append((to, subject, body)) or True)
    return sent


def code_for(outbox, email):
    bodies = [body for to, _, body in outbox if to == email]
    return re.search(r"\b(\d{6})\b", bodies[-1]).group(1)


def signup(client, username="ravi", email="ravi@example.com", password=PW):
    return client.post("/register", data={"username": username, "email": email,
                                          "password": password})


def verify(client, code):
    return client.post("/register/verify", data={"code": code})


def full_signup(client, outbox, name="ravi", email=None):
    email = email or f"{name}@example.com"
    assert signup(client, name, email).status_code == 303
    r = verify(client, code_for(outbox, email))
    assert r.status_code == 303 and r.headers["location"] == "/dashboard"


def count(app, model):
    with app.state.session_factory() as db:
        return db.query(model).count()


def pending_row(app, email="ravi@example.com"):
    with app.state.session_factory() as db:
        return db.get(PendingSignup, email)


def change_pending(app, email="ravi@example.com", **fields):
    with app.state.session_factory() as db:
        row = db.get(PendingSignup, email)
        for name, value in fields.items():
            setattr(row, name, value)
        db.commit()


# ---------- the normal path ----------

def test_signup_works_as_before_when_email_is_not_set_up(client, app):
    r = signup(client)
    assert r.status_code == 303 and r.headers["location"] == "/dashboard"
    with app.state.session_factory() as db:
        assert db.query(User).one().email_verified_at is None
    assert count(app, PendingSignup) == 0


def test_no_account_exists_until_the_code_is_entered(client, app, outbox):
    r = signup(client)
    assert r.status_code == 303 and r.headers["location"] == "/register/verify"
    assert count(app, User) == 0 and count(app, PendingSignup) == 1
    assert [to for to, _, _ in outbox] == ["ravi@example.com"]
    assert client.get("/dashboard").status_code == 303            # not logged in
    assert "ravi@example.com" in client.get("/register/verify").text
    assert client.post("/login", data={"identifier": "ravi", "password": PW}).status_code == 400


def test_the_right_code_creates_the_account_and_logs_in(client, app, outbox):
    signup(client)
    r = verify(client, code_for(outbox, "ravi@example.com"))
    assert r.status_code == 303 and r.headers["location"] == "/dashboard"
    with app.state.session_factory() as db:
        user = db.query(User).one()
        assert user.email_verified_at is not None and user.last_login_at is not None
        assert user.username == "ravi" and user.email == "ravi@example.com"
    assert count(app, PendingSignup) == 0
    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200 and "Welcome to Link Shortener" in dashboard.text


def test_the_password_is_only_ever_stored_hashed(client, app, outbox):
    signup(client)
    stored = pending_row(app).password_hash
    assert stored.startswith("$2") and PW not in stored
    verify(client, code_for(outbox, "ravi@example.com"))
    client.post("/logout")
    assert client.post("/login", data={"identifier": "ravi", "password": PW}).status_code == 303


# ---------- wrong, expired and repeated codes ----------

def test_wrong_codes_are_refused_and_five_of_them_cancel_the_sign_up(client, app, outbox):
    signup(client)
    right = code_for(outbox, "ravi@example.com")
    wrong = "000000" if right != "000000" else "111111"
    for _ in range(4):
        r = verify(client, wrong)
        assert r.status_code == 400 and "not correct" in r.text
    r = verify(client, wrong)  # the fifth wrong guess
    assert r.status_code == 303 and r.headers["location"] == "/register"
    assert count(app, PendingSignup) == 0
    assert verify(client, right).headers["location"] == "/register"   # too late now
    assert count(app, User) == 0


def test_an_expired_code_does_not_work(client, app, outbox):
    signup(client)
    change_pending(app, expires_at=utcnow() - timedelta(minutes=1))
    assert client.get("/register/verify").headers["location"] == "/register"
    assert verify(client, code_for(outbox, "ravi@example.com")).headers["location"] == "/register"
    assert count(app, User) == 0
    assert "expired" in client.get("/register").text


def test_the_verify_page_needs_a_sign_up_in_progress(client, outbox):
    assert client.get("/register/verify").headers["location"] == "/register"
    r = client.post("/register/verify", data={"code": "123456"})
    assert r.headers["location"] == "/register"


def test_cancelling_removes_the_pending_sign_up(client, app, outbox):
    signup(client)
    r = client.post("/register/cancel")
    assert r.status_code == 303 and r.headers["location"] == "/register"
    assert count(app, PendingSignup) == 0
    assert client.get("/register/verify").headers["location"] == "/register"


# ---------- sending a new code ----------

def test_resend_waits_a_minute_then_replaces_the_code(client, app, outbox, monkeypatch):
    codes = iter(["111111", "222222"])
    monkeypatch.setattr("app.routers.auth.new_code", lambda: next(codes))
    signup(client)
    r = client.post("/register/resend")
    assert r.headers["location"] == "/register/verify" and len(outbox) == 1   # too soon
    assert "Please wait" in client.get("/register/verify").text
    change_pending(app, sent_at=utcnow() - timedelta(minutes=2))
    client.post("/register/resend")
    assert len(outbox) == 2 and code_for(outbox, "ravi@example.com") == "222222"
    assert verify(client, "111111").status_code == 400                      # the old code is dead
    assert verify(client, "222222").headers["location"] == "/dashboard"


# ---------- limits ----------

def test_one_email_can_only_be_sent_five_codes_an_hour(client, app, outbox):
    for _ in range(5):
        assert signup(client).status_code == 303
        change_pending(app, sent_at=utcnow() - timedelta(minutes=5))   # skip the 1-minute wait
    r = signup(client)
    assert r.status_code == 429 and "Too many codes were requested" in r.text
    assert len(outbox) == 5


def test_the_daily_cap_protects_the_email_allowance(make_client, app, outbox, monkeypatch):
    monkeypatch.setattr(settings, "signup_code_daily_limit", 2)
    first, second, third = make_client(), make_client(), make_client()
    assert signup(first, "one", "one@example.com").status_code == 303
    assert signup(second, "two", "two@example.com").status_code == 303
    r = signup(third, "three", "three@example.com")
    assert r.status_code == 429 and "very busy" in r.text
    assert len(outbox) == 2 and pending_row(app, "three@example.com") is None


def test_old_unfinished_sign_ups_are_tidied_away(client, app, outbox):
    signup(client, "old", "old@example.com")
    change_pending(app, "old@example.com", expires_at=utcnow() - timedelta(days=2))
    signup(client, "new", "new@example.com")
    assert pending_row(app, "old@example.com") is None
    assert pending_row(app, "new@example.com") is not None


# ---------- names and emails that are already used ----------

def test_taken_names_and_emails_are_refused_before_any_email_is_sent(make_client, outbox):
    full_signup(make_client(), outbox, "ravi")
    sent_so_far = len(outbox)
    same_name = signup(make_client(), "ravi", "other@example.com")
    same_email = signup(make_client(), "other", "ravi@example.com")
    assert same_name.status_code == 400 and same_email.status_code == 400
    assert "already registered" in same_name.text
    assert len(outbox) == sent_so_far


def test_waiting_for_a_code_does_not_reserve_a_username_or_email(make_client, app, outbox):
    slow, quick = make_client(), make_client()
    signup(slow, "ravi", "ravi@example.com")                 # asks for a code but does not enter it
    full_signup(quick, outbox, "ravi", "someone.else@example.com")   # same username, finishes first
    # the slow one finally enters the right code, and is told the name was taken meanwhile
    r = verify(slow, code_for(outbox, "ravi@example.com"))
    assert r.status_code == 303 and r.headers["location"] == "/register"
    assert "just taken" in slow.get("/register").text
    assert count(app, User) == 1


# ---------- when sending fails ----------

def test_if_the_email_cannot_be_sent_nothing_is_left_behind(client, app, monkeypatch):
    monkeypatch.setattr(settings, "email_backend", "console")
    monkeypatch.setattr("app.routers.auth.send_email", lambda *args: False)
    r = signup(client)
    assert r.status_code == 503 and "could not send the email" in r.text
    assert count(app, PendingSignup) == 0 and count(app, User) == 0
    assert client.get("/register/verify").headers["location"] == "/register"


# ---------- language ----------

def test_the_email_and_page_follow_the_visitors_language(client, app, outbox):
    client.cookies.set("lang", "hi")
    signup(client)
    to, subject, body = outbox[-1]
    assert subject == "आपका Link Shortener साइन-अप कोड" and "मिनट" in body
    assert "सत्यापित करें और खाता बनाएँ" in client.get("/register/verify").text
    r = verify(client, code_for(outbox, "ravi@example.com"))
    assert "lang=hi" in r.headers["set-cookie"]
    with app.state.session_factory() as db:
        assert db.query(User).one().language == "hi"


def test_the_verify_page_is_translated_into_gujarati(client, outbox):
    client.cookies.set("lang", "gu")
    signup(client)
    page = client.get("/register/verify").text
    assert "ચકાસો અને એકાઉન્ટ બનાવો" in page and "બીજો ઇમેઇલ વાપરો" in page


# ---------- the rest of the system ----------

def test_changing_your_email_with_a_code_marks_it_confirmed(alice, app, monkeypatch):
    sent = []
    monkeypatch.setattr(settings, "email_backend", "console")
    monkeypatch.setattr("app.routers.account.send_email",
                        lambda to, subject, body: sent.append(body) or True)
    with app.state.session_factory() as db:
        assert db.query(User).one().email_verified_at is None
    alice.post("/account/email/request", data={"new_email": "new@example.com", "password": PW})
    alice.post("/account/email/verify", data={"code": re.search(r"\b(\d{6})\b", sent[-1]).group(1)})
    with app.state.session_factory() as db:
        user = db.query(User).one()
        assert user.email == "new@example.com" and user.email_verified_at is not None


def test_existing_accounts_are_marked_confirmed_by_the_migration(tmp_path, monkeypatch):
    from alembic.config import Config
    from sqlalchemy import create_engine, text

    from alembic import command

    root = Path(__file__).resolve().parent.parent
    url = f"sqlite:///{tmp_path / 'old.db'}"
    monkeypatch.setattr(settings, "database_url", url)  # alembic's env.py reads this
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("path_separator", "os")  # avoids an alembic deprecation notice

    command.upgrade(config, "0005")   # the database as it was before this feature
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (username, email, password_hash, created_at) "
                          "VALUES ('old', 'old@example.com', 'x', '2026-01-02 03:04:05')"))
    command.upgrade(config, "head")
    with engine.connect() as conn:
        row = conn.execute(text("SELECT created_at, email_verified_at FROM users")).one()
    assert row.email_verified_at is not None and row.email_verified_at == row.created_at
