"""Forgot password: an emailed, one-hour, single-use link for choosing a new password."""
import re

import pytest
from itsdangerous import URLSafeTimedSerializer

from app.config import settings
from app.models import User
from tests.conftest import register

PW = "password123"
NEW_PW = "brand-new-pass"
EMAIL = "alice@example.com"


@pytest.fixture()
def outbox(alice, monkeypatch):
    """Switch email on (after alice exists) and collect what would be sent: (to, subject, body)."""
    sent = []
    monkeypatch.setattr(settings, "email_backend", "console")
    monkeypatch.setattr("app.routers.auth.send_email",
                        lambda to, subject, body: sent.append((to, subject, body)) or True)
    return sent


@pytest.fixture()
def visitor(make_client):
    """A browser that is not logged in."""
    return make_client()


@pytest.fixture()
def bob(alice, make_client):
    """A second account, made before email is switched on (list it before `outbox`)."""
    client = make_client()
    register(client, "bobby")
    return client


@pytest.fixture()
def limits(redis_fake):
    redis_fake.flushall()
    return redis_fake


def ask(client, email=EMAIL, **kwargs):
    return client.post("/forgot-password", data={"email": email}, **kwargs)


def link(outbox) -> str:
    return re.search(r"https?://\S+/reset-password/\S+", outbox[-1][2]).group(0)


def path(outbox) -> str:
    return "/reset-password/" + link(outbox).rsplit("/", 1)[1]


def set_password(client, token_path, new=NEW_PW, confirm=None):
    return client.post(token_path, data={"new_password": new,
                                         "confirm_password": new if confirm is None else confirm})


def forged(payload, salt="password-reset") -> str:
    """A link signed with our real secret, but carrying whatever the test wants inside."""
    signer = URLSafeTimedSerializer(settings.secret_key, salt=salt)
    return "/reset-password/" + signer.dumps(payload)


def can_log_in(client, password):
    return client.post("/login", data={"identifier": "alice", "password": password}
                       ).status_code == 303


# ---------- when email is (not) set up ----------

def test_login_offers_the_link_only_when_email_is_set_up(visitor, outbox, monkeypatch):
    assert 'href="/forgot-password"' in visitor.get("/login").text
    monkeypatch.setattr(settings, "email_backend", "none")
    assert "forgot-password" not in visitor.get("/login").text


def test_the_link_is_still_there_after_a_wrong_password(visitor, outbox):
    page = visitor.post("/login", data={"identifier": "alice", "password": "nope-nope"}).text
    assert 'href="/forgot-password"' in page


def test_without_email_the_page_says_so_and_nothing_is_sent(alice, visitor):
    page = visitor.get("/forgot-password")
    assert page.status_code == 200 and "not available on this server yet" in page.text
    assert 'action="/forgot-password"' not in page.text
    assert ask(visitor).status_code == 503


# ---------- asking for the link ----------

def test_the_link_is_emailed_to_the_account(visitor, outbox):
    r = ask(visitor)
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert [to for to, _, _ in outbox] == [EMAIL]
    assert outbox[0][1] == "Reset your Link Shortener password"
    assert re.search(r"/reset-password/[\w.-]+", outbox[0][2])
    assert "one hour" in outbox[0][2]


def test_an_unknown_address_gets_exactly_the_same_answer(visitor, make_client, outbox):
    known = ask(visitor)
    stranger = make_client()
    unknown = ask(stranger, "nobody@example.com")
    assert (known.status_code, known.headers["location"]) == \
           (unknown.status_code, unknown.headers["location"])
    assert len(outbox) == 1                                     # nothing sent for the stranger
    page = stranger.get("/login").text                          # but it says the same thing
    assert "we sent a link" in page and "nobody@example.com" in page


def test_the_address_is_not_case_sensitive(visitor, outbox):
    assert ask(visitor, "  ALICE@Example.COM ").status_code == 303
    assert [to for to, _, _ in outbox] == [EMAIL]


def test_a_badly_typed_address_is_refused_and_nothing_is_sent(visitor, outbox):
    r = ask(visitor, "not-an-email")
    assert r.status_code == 400 and "Enter a valid email address." in r.text
    assert "not-an-email" in r.text                             # what they typed stays in the box
    assert outbox == []


def test_the_email_follows_the_accounts_saved_language(visitor, outbox, app):
    with app.state.session_factory() as db:
        db.query(User).filter_by(username="alice").one().language = "hi"
        db.commit()
    ask(visitor)
    _, subject, body = outbox[-1]
    assert subject == "अपना Link Shortener पासवर्ड रीसेट करें"
    assert "घंटे" in body and "/reset-password/" in body


def test_a_logged_in_person_is_sent_to_the_dashboard(alice, outbox):
    assert alice.get("/forgot-password").headers["location"] == "/dashboard"


# ---------- the address inside the email ----------

def test_the_link_uses_the_servers_address_not_the_host_header(visitor, outbox, monkeypatch):
    monkeypatch.setattr(settings, "base_url", "https://short.example")
    ask(visitor, headers={"host": "evil.example"})
    assert link(outbox).startswith("https://short.example/reset-password/")
    assert "evil" not in outbox[-1][2]


def test_on_render_the_services_own_address_is_used(visitor, outbox, monkeypatch):
    monkeypatch.setattr(settings, "base_url", "")
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://link-shortener-tcom.onrender.com/")
    ask(visitor, headers={"host": "evil.example"})
    assert link(outbox).startswith("https://link-shortener-tcom.onrender.com/reset-password/")


def test_without_any_setting_the_request_address_is_the_last_resort(visitor, outbox, monkeypatch):
    monkeypatch.setattr(settings, "base_url", "")
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    ask(visitor)
    assert link(outbox).startswith("http://testserver/reset-password/")


# ---------- choosing the new password ----------

def test_the_whole_flow(visitor, outbox):
    ask(visitor)
    page = visitor.get(path(outbox))
    assert page.status_code == 200 and 'name="new_password"' in page.text
    assert page.headers["cache-control"] == "no-store"

    r = set_password(visitor, path(outbox))
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert "Password changed" in visitor.get("/login").text
    assert can_log_in(visitor, NEW_PW) and not can_log_in(visitor, PW)


def test_the_new_password_is_stored_hashed(visitor, outbox, app):
    ask(visitor)
    set_password(visitor, path(outbox))
    with app.state.session_factory() as db:
        stored = db.query(User).filter_by(username="alice").one().password_hash
    assert stored.startswith("$2") and NEW_PW not in stored


def test_resetting_does_not_log_anyone_in(visitor, outbox):
    ask(visitor)
    set_password(visitor, path(outbox))
    assert visitor.get("/dashboard").headers["location"] == "/login"


def test_reading_the_link_proves_the_mailbox(visitor, outbox, app):
    with app.state.session_factory() as db:
        assert db.query(User).filter_by(username="alice").one().email_verified_at is None
    ask(visitor)
    set_password(visitor, path(outbox))
    with app.state.session_factory() as db:
        assert db.query(User).filter_by(username="alice").one().email_verified_at is not None


def test_a_link_works_only_once(visitor, outbox):
    ask(visitor)
    old_link = path(outbox)
    set_password(visitor, old_link)
    r = visitor.get(old_link)
    assert r.status_code == 303 and r.headers["location"] == "/forgot-password"
    assert "expired or was already used" in visitor.get("/forgot-password").text
    again = set_password(visitor, old_link, new="another-pass-1")
    assert again.headers["location"] == "/forgot-password"
    assert can_log_in(visitor, NEW_PW) and not can_log_in(visitor, "another-pass-1")


def test_an_older_link_stays_valid_until_the_password_changes(visitor, outbox):
    ask(visitor)
    first = path(outbox)
    ask(visitor)
    assert visitor.get(first).status_code == 200 and visitor.get(path(outbox)).status_code == 200
    set_password(visitor, path(outbox))
    assert visitor.get(first).headers["location"] == "/forgot-password"   # now both are dead


def test_a_link_expires_after_an_hour(visitor, outbox, monkeypatch):
    from app import resettoken

    assert resettoken.MAX_AGE_SECONDS == 3600
    ask(visitor)
    monkeypatch.setattr(resettoken, "MAX_AGE_SECONDS", -1)  # as if the hour had passed
    assert visitor.get(path(outbox)).headers["location"] == "/forgot-password"
    assert set_password(visitor, path(outbox)).headers["location"] == "/forgot-password"
    assert can_log_in(visitor, PW)


def test_changing_the_password_in_account_cancels_links_still_out_there(alice, visitor, outbox):
    ask(visitor)
    alice.post("/account/password", data={"current_password": PW, "new_password": "changed-it-1"})
    assert visitor.get(path(outbox)).headers["location"] == "/forgot-password"


def test_changing_the_email_cancels_links_sent_to_the_old_address(visitor, outbox, app):
    ask(visitor)
    with app.state.session_factory() as db:
        db.query(User).filter_by(username="alice").one().email = "moved@example.com"
        db.commit()
    assert visitor.get(path(outbox)).headers["location"] == "/forgot-password"


def test_made_up_and_damaged_links_are_refused(visitor, outbox):
    ask(visitor)
    good = path(outbox)
    for bad in (
        "/reset-password/garbage",
        "/reset-password/a.b.c",
        good[:-1] + ("A" if good[-1] != "A" else "B"),            # one character changed
        forged({"u": 1, "f": "x"}, salt="something-else"),
        forged("not a dict"),
        forged({"u": 999, "f": "x"}),                             # right signature, wrong person
    ):
        r = visitor.get(bad)
        assert r.status_code == 303 and r.headers["location"] == "/forgot-password", bad
        assert set_password(visitor, bad).headers["location"] == "/forgot-password", bad
    assert can_log_in(visitor, PW)


def test_one_persons_link_cannot_reset_another_persons_password(bob, visitor, outbox):
    ask(visitor)                                                 # a link for alice
    set_password(visitor, path(outbox), new="alice-new-pass")
    assert bob.post("/login", data={"identifier": "bobby", "password": PW}).status_code == 303


def test_a_short_password_is_refused_and_the_link_keeps_working(visitor, outbox):
    ask(visitor)
    r = set_password(visitor, path(outbox), new="short12")
    assert r.status_code == 400 and "Password must be 8-72 characters." in r.text
    assert can_log_in(visitor, PW)
    assert visitor.get(path(outbox)).status_code == 200


def test_two_different_passwords_are_refused(visitor, outbox):
    ask(visitor)
    r = set_password(visitor, path(outbox), new=NEW_PW, confirm="something-else")
    assert r.status_code == 400 and "do not match" in r.text
    assert can_log_in(visitor, PW)
    assert visitor.get(path(outbox)).status_code == 200


def test_the_link_is_not_mistaken_for_a_short_link(visitor):
    r = visitor.get("/reset-password/whatever")
    assert r.status_code == 303 and r.headers["location"] == "/forgot-password"


# ---------- limits ----------

def test_asking_again_and_again_for_one_address_sends_at_most_three(visitor, outbox, limits):
    answers = [ask(visitor).status_code for _ in range(5)]
    assert answers == [303] * 5                                  # always the same answer
    assert len(outbox) == 3


def test_one_visitor_cannot_ask_more_than_ten_times_an_hour(visitor, outbox, limits):
    for n in range(10):
        assert ask(visitor, f"person{n}@example.com").status_code == 303
    r = ask(visitor, "person11@example.com")
    assert r.status_code == 429 and "Too many attempts" in r.text


def test_the_site_wide_daily_budget_protects_the_email_quota(make_client, outbox, limits,
                                                             monkeypatch):
    monkeypatch.setattr(settings, "reset_email_daily_limit", 1)
    assert ask(make_client()).status_code == 303
    r = ask(make_client(), "other@example.com")
    assert r.status_code == 429 and "very busy" in r.text
    assert len(outbox) == 1


def test_trying_passwords_on_the_reset_page_is_limited(visitor, outbox, limits):
    ask(visitor)
    for _ in range(20):
        assert set_password(visitor, "/reset-password/garbage").status_code == 303
    r = set_password(visitor, "/reset-password/garbage")
    assert r.status_code == 429


# ---------- languages ----------

@pytest.mark.parametrize("lang,script", [("hi", re.compile(r"[\u0900-\u097F]")),
                                         ("gu", re.compile(r"[\u0A80-\u0AFF]"))])
def test_the_pages_are_translated(visitor, outbox, lang, script):
    visitor.cookies.set("lang", lang)
    ask(visitor)
    asking, choosing = visitor.get("/forgot-password").text, visitor.get(path(outbox)).text
    for page in (asking, choosing):
        assert f'<html lang="{lang}"' in page and script.search(page)
    assert "Reset your password</h1>" not in asking
    assert "Choose a new password</h1>" not in choosing
    assert "Forgot password?" not in visitor.get("/login").text


def test_messages_after_the_flow_are_translated(visitor, outbox):
    visitor.cookies.set("lang", "hi")
    ask(visitor)
    assert "हमने उसका पासवर्ड रीसेट करने का लिंक भेज दिया है" in visitor.get("/login").text
    old_link = path(outbox)
    set_password(visitor, old_link)
    assert "पासवर्ड बदल दिया गया" in visitor.get("/login").text
    visitor.get(old_link)                                        # now used up
    assert "यह रीसेट लिंक समाप्त हो गया है" in visitor.get("/forgot-password").text
