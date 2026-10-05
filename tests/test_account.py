import re
from datetime import timedelta
from pathlib import Path

import pytest

from app.config import settings
from app.models import EmailChange, Link, User, UsernameAlias, utcnow
from app.profile import AVATARS
from tests.conftest import register

PW = "password123"


def make_link(client, slug="hello", url="https://example.com/page"):
    return client.post("/dashboard/links", data={"original_url": url, "slug": slug})


@pytest.fixture()
def sent(monkeypatch):
    """Pretend email works and capture what would have been sent."""
    outbox = []
    monkeypatch.setattr(settings, "email_backend", "console")
    monkeypatch.setattr(
        "app.routers.account.send_email",
        lambda to, subject, body: outbox.append((to, body)) or True,
    )
    return outbox


def code_from(outbox):
    return re.search(r"\b(\d{6})\b", outbox[-1][1]).group(1)


def get_user(app, username):
    with app.state.session_factory() as db:
        return db.query(User).filter_by(username=username).one()


# ---------- avatars ----------

def test_all_twenty_avatar_files_exist():
    assert len(AVATARS) == 20
    folder = Path(__file__).resolve().parent.parent / "app" / "static" / "avatars"
    for key in AVATARS:
        assert (folder / f"{key}.svg").is_file(), key


def test_set_avatar_and_navbar_shows_it(alice):
    alice.post("/account/avatar", data={"avatar": "panda"})
    assert "/static/avatars/panda.svg" in alice.get("/dashboard").text


def test_invalid_avatar_rejected(alice, app):
    before = get_user(app, "alice").avatar
    alice.post("/account/avatar", data={"avatar": "../../etc/passwd"})
    assert get_user(app, "alice").avatar == before


def test_account_page_needs_login(client):
    assert client.get("/account").status_code == 303
    assert client.post("/account/avatar", data={"avatar": "cat"}).status_code == 303


def test_account_page_renders(alice):
    page = alice.get("/account")
    assert page.status_code == 200
    assert page.text.count('type="radio" name="avatar"') == 20
    assert "Delete account" in page.text


# ---------- theme ----------

def test_theme_saved_and_applied(alice, app):
    alice.post("/account/theme", data={"theme": "dark"})
    assert get_user(app, "alice").theme == "dark"
    assert 'data-theme="dark"' in alice.get("/dashboard").text


def test_theme_cookie_applies_when_logged_out(alice):
    alice.post("/account/theme", data={"theme": "light"})
    alice.post("/logout")
    assert 'data-theme="light"' in alice.get("/login").text


def test_invalid_theme_rejected(alice, app):
    alice.post("/account/theme", data={"theme": "neon"})
    assert get_user(app, "alice").theme == "system"


def test_default_theme_is_system(client):
    assert 'data-theme="system"' in client.get("/login").text


# ---------- username ----------

def test_username_change_keeps_old_links_working(alice):
    make_link(alice, "portfolio")
    r = alice.post("/account/username", data={"new_username": "alice2", "password": PW})
    assert r.status_code == 303
    assert alice.get("/alice2/portfolio").status_code == 302
    assert alice.get("/alice/portfolio").status_code == 302  # old name still works
    assert "alice2/portfolio" in alice.get("/dashboard").text


def test_old_username_cannot_be_taken_by_someone_else(alice, make_client):
    alice.post("/account/username", data={"new_username": "alice2", "password": PW})
    mallory = make_client()
    assert register(mallory, "alice").status_code == 400  # reserved for alice's old links
    register(mallory, "mallory")
    r = mallory.post("/account/username", data={"new_username": "alice", "password": PW})
    assert "taken" in mallory.get("/account").text
    assert r.status_code == 303


def test_username_change_needs_correct_password(alice, app):
    alice.post("/account/username", data={"new_username": "alice2", "password": "wrong-pass"})
    assert get_user(app, "alice")


def test_username_rules(alice, app):
    for bad in ("ab", "admin", "account", "has space", "alice"):
        alice.post("/account/username", data={"new_username": bad, "password": PW})
    assert get_user(app, "alice")  # nothing changed


def test_username_taken_by_existing_user(alice, make_client):
    bob = make_client()
    register(bob, "bob")
    alice.post("/account/username", data={"new_username": "bob", "password": PW})
    assert "taken" in alice.get("/account").text


def test_can_take_back_own_old_username(alice, app):
    alice.post("/account/username", data={"new_username": "alice2", "password": PW})
    alice.post("/account/username", data={"new_username": "alice", "password": PW})
    assert get_user(app, "alice")
    with app.state.session_factory() as db:
        names = {a.username for a in db.query(UsernameAlias).all()}
    assert names == {"alice2"}


def test_old_username_limit(alice, app):
    for i in range(1, 7):
        alice.post("/account/username", data={"new_username": f"alice_{i}", "password": PW})
    with app.state.session_factory() as db:
        assert db.query(UsernameAlias).count() == 5
    assert get_user(app, "alice_5")  # the 6th change was refused


# ---------- password ----------

def test_change_password(alice):
    alice.post("/account/password", data={"current_password": PW, "new_password": "newpass999"})
    alice.post("/logout")
    assert alice.post("/login", data={"identifier": "alice", "password": PW}).status_code == 400
    r = alice.post("/login", data={"identifier": "alice", "password": "newpass999"})
    assert r.status_code == 303


def test_change_password_rejects_wrong_current_or_short_new(alice):
    bad_current = {"current_password": "nope-nope", "new_password": "newpass999"}
    alice.post("/account/password", data=bad_current)
    alice.post("/account/password", data={"current_password": PW, "new_password": "short"})
    alice.post("/logout")
    assert alice.post("/login", data={"identifier": "alice", "password": PW}).status_code == 303


# ---------- email change with OTP ----------

def test_email_change_flow(alice, app, sent):
    r = alice.post("/account/email/request", data={"new_email": "New@Example.com", "password": PW})
    assert r.headers["location"] == "/account/email/verify"
    assert sent[-1][0] == "new@example.com"  # the code goes to the NEW address
    assert get_user(app, "alice").email == "alice@example.com"  # not changed yet

    r = alice.post("/account/email/verify", data={"code": code_from(sent)})
    assert r.status_code == 303
    assert get_user(app, "alice").email == "new@example.com"
    with app.state.session_factory() as db:
        assert db.query(EmailChange).count() == 0


def test_wrong_code_does_not_change_email(alice, app, sent):
    alice.post("/account/email/request", data={"new_email": "new@example.com", "password": PW})
    right = code_from(sent)
    wrong = "000000" if right != "000000" else "111111"
    r = alice.post("/account/email/verify", data={"code": wrong})
    assert r.status_code == 400 and "not correct" in r.text
    assert get_user(app, "alice").email == "alice@example.com"


def test_five_wrong_codes_cancel_the_change(alice, app, sent):
    alice.post("/account/email/request", data={"new_email": "new@example.com", "password": PW})
    right = code_from(sent)
    wrong = "000000" if right != "000000" else "111111"
    for _ in range(5):
        alice.post("/account/email/verify", data={"code": wrong})
    alice.post("/account/email/verify", data={"code": right})  # too late
    assert get_user(app, "alice").email == "alice@example.com"


def test_expired_code_rejected(alice, app, sent):
    alice.post("/account/email/request", data={"new_email": "new@example.com", "password": PW})
    with app.state.session_factory() as db:
        db.get(EmailChange, 1).expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    alice.post("/account/email/verify", data={"code": code_from(sent)})
    assert get_user(app, "alice").email == "alice@example.com"


def test_email_request_needs_password_and_unique_email(alice, make_client, sent):
    bob = make_client()
    register(bob, "bob")
    wrong_pw = {"new_email": "x@example.com", "password": "wrong-pass"}
    alice.post("/account/email/request", data=wrong_pw)
    alice.post("/account/email/request", data={"new_email": "bob@example.com", "password": PW})
    alice.post("/account/email/request", data={"new_email": "alice@example.com", "password": PW})
    alice.post("/account/email/request", data={"new_email": "not-an-email", "password": PW})
    assert sent == []


def test_resend_has_cooldown(alice, sent):
    alice.post("/account/email/request", data={"new_email": "new@example.com", "password": PW})
    alice.post("/account/email/resend")
    assert len(sent) == 1  # blocked: asked again within 60 seconds


def test_email_change_disabled_without_provider(alice, monkeypatch):
    monkeypatch.setattr(settings, "email_backend", "none")
    assert "not available" in alice.get("/account").text
    r = alice.post("/account/email/request", data={"new_email": "n@example.com", "password": PW})
    assert r.headers["location"].startswith("/account")


def test_email_send_failure_is_reported(alice, app, monkeypatch):
    monkeypatch.setattr(settings, "email_backend", "console")
    monkeypatch.setattr("app.routers.account.send_email", lambda *a: False)
    alice.post("/account/email/request", data={"new_email": "n@example.com", "password": PW})
    with app.state.session_factory() as db:
        assert db.query(EmailChange).count() == 0


def test_mailer_uses_brevo_api(monkeypatch):
    import httpx

    from app import mailer

    calls = {}

    def fake_post(url, headers, json, timeout):
        calls.update(url=url, headers=headers, json=json)
        return httpx.Response(201, request=httpx.Request("POST", url))

    monkeypatch.setattr(settings, "email_backend", "brevo")
    monkeypatch.setattr(settings, "brevo_api_key", "KEY")
    monkeypatch.setattr(settings, "mail_from", "me@example.com")
    monkeypatch.setattr(mailer.httpx, "post", fake_post)
    assert mailer.send_email("to@example.com", "Hi", "Body") is True
    assert calls["url"].startswith("https://api.brevo.com/")
    assert calls["headers"]["api-key"] == "KEY"
    assert calls["json"]["to"] == [{"email": "to@example.com"}]


# ---------- delete account ----------

def test_delete_account(alice, make_client, app, redis_fake):
    make_link(alice, "gone")
    alice.get("/alice/gone")  # fills the cache and records a click
    r = alice.post("/account/delete", data={"confirm": "alice", "password": PW})
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert redis_fake.get("link:alice:gone") is None
    assert alice.get("/alice/gone").status_code == 404
    assert alice.get("/dashboard").status_code == 303  # logged out
    with app.state.session_factory() as db:
        assert db.query(User).count() == 0 and db.query(Link).count() == 0
    # the name is free again
    assert register(make_client(), "alice").status_code == 303


def test_delete_requires_username_and_password(alice, app):
    alice.post("/account/delete", data={"confirm": "wrong", "password": PW})
    alice.post("/account/delete", data={"confirm": "alice", "password": "wrong-pass"})
    assert get_user(app, "alice")


def test_delete_removes_old_username_cache_and_aliases(alice, app, redis_fake):
    make_link(alice, "keep")
    alice.post("/account/username", data={"new_username": "alice2", "password": PW})
    alice.get("/alice/keep")  # cached under the OLD name
    assert redis_fake.get("link:alice:keep")
    alice.post("/account/delete", data={"confirm": "alice2", "password": PW})
    assert redis_fake.get("link:alice:keep") is None
    with app.state.session_factory() as db:
        assert db.query(UsernameAlias).count() == 0


def test_deleting_a_link_clears_cache_under_old_username(alice, redis_fake):
    make_link(alice, "tmp")
    alice.post("/account/username", data={"new_username": "alice2", "password": PW})
    alice.get("/alice/tmp")
    assert redis_fake.get("link:alice:tmp")
    alice.post("/dashboard/links/1/delete")
    assert redis_fake.get("link:alice:tmp") is None
    assert alice.get("/alice/tmp").status_code == 404


def test_stylesheet_url_is_versioned(client):
    html = client.get("/login").text
    assert re.search(r'/static/style\.css\?v=[0-9a-f]{10}"', html)
