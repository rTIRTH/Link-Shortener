from app.config import settings
from tests.conftest import register


def test_admin_hidden_from_anonymous_and_normal_users(alice, make_client, monkeypatch):
    monkeypatch.setattr(settings, "admin_usernames", {"someoneelse"})
    anon = make_client()
    assert anon.get("/admin").status_code == 303  # sent to /login
    assert alice.get("/admin").status_code == 404  # logged in but not admin
    assert "Admin" not in alice.get("/dashboard").text.split("<main>")[0]


def test_admin_sees_users_and_stats(alice, make_client, monkeypatch):
    monkeypatch.setattr(settings, "admin_usernames", {"alice"})
    bob = make_client()
    register(bob, "bob")
    bob.post("/dashboard/links", data={"original_url": "https://example.com", "slug": "bobby"})
    bob.get("/bob/bobby")

    page = alice.get("/admin")
    assert page.status_code == 200
    assert "bob@example.com" in page.text and "alice@example.com" in page.text
    assert "bob/bobby" in page.text
    assert ">Admin</a>" in alice.get("/dashboard").text


def test_last_login_is_recorded(alice, app, monkeypatch):
    from app.models import User

    with app.state.session_factory() as db:
        first = db.query(User).filter_by(username="alice").one().last_login_at
    assert first is not None
    alice.post("/logout")
    alice.post("/login", data={"identifier": "alice", "password": "password123"})
    with app.state.session_factory() as db:
        second = db.query(User).filter_by(username="alice").one().last_login_at
    assert second >= first
