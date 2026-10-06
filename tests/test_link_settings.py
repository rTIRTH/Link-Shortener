import csv
import io
from datetime import timedelta

import pytest

from app.models import Click, Link, utcnow
from app.utils import parse_moment, validate_link_password

URL = "https://example.com/secret/page"


def iso(delta):
    return (utcnow() + delta).isoformat()


def make(client, slug="lnk", **fields):
    data = {"original_url": URL, "slug": slug, **fields}
    return client.post("/dashboard/links", data=data)


def link_row(app, slug="lnk"):
    with app.state.session_factory() as db:
        return db.query(Link).filter_by(slug=slug).one()


def click_total(app):
    with app.state.session_factory() as db:
        return db.query(Click).count()


# ---------- parsing ----------

def test_parse_moment_variants():
    assert parse_moment("", "") is None
    date_only_end = parse_moment("", "2030-05-01", end_of_day=True)
    assert (date_only_end.hour, date_only_end.minute, date_only_end.second) == (23, 59, 59)
    assert parse_moment("", "2030-05-01").hour == 0
    exact = parse_moment("2030-05-01T10:30:00.000Z", "ignored")
    assert (exact.hour, exact.minute, exact.utcoffset()) == (10, 30, timedelta(0))
    # an offset is converted to UTC
    assert parse_moment("2030-05-01T10:30:00+05:30", "").hour == 5
    for bad in ("not a date", "1999-01-01", "2500-01-01"):
        with pytest.raises(ValueError):
            parse_moment("", bad)


def test_link_password_rules():
    assert validate_link_password("abcd") == "abcd"
    for bad in ("abc", "x" * 73):
        with pytest.raises(ValueError):
            validate_link_password(bad)


# ---------- start and end times ----------

def test_link_not_active_before_start(alice, app):
    make(alice, starts_at_utc=iso(timedelta(days=1)))
    r = alice.get("/alice/lnk")
    assert r.status_code == 403 and "not active yet" in r.text
    assert click_total(app) == 0


def test_link_works_after_start_time_passes(alice, app):
    make(alice, starts_at_utc=iso(timedelta(days=1)))
    with app.state.session_factory() as db:
        db.query(Link).one().starts_at = utcnow() - timedelta(minutes=1)
        db.commit()
    assert alice.get("/alice/lnk").status_code == 302


def test_start_in_the_past_is_allowed(alice):
    make(alice, starts_at_utc=iso(-timedelta(days=1)))
    assert alice.get("/alice/lnk").status_code == 302


def test_end_time_stops_the_link(alice, app):
    make(alice, expires_at_utc=iso(timedelta(hours=2)))
    assert alice.get("/alice/lnk").status_code == 302
    with app.state.session_factory() as db:
        db.query(Link).one().expires_at = utcnow() - timedelta(seconds=5)
        db.commit()
    assert alice.get("/alice/lnk").status_code == 410


def test_schedule_validation(alice):
    make(alice, "bad1", starts_at_utc=iso(timedelta(days=3)), expires_at_utc=iso(timedelta(days=2)))
    make(alice, "bad2", expires_at_utc=iso(-timedelta(hours=1)))
    make(alice, "bad3", starts_at="garbage")
    for slug in ("bad1", "bad2", "bad3"):
        assert alice.get(f"/alice/{slug}").status_code == 404


def test_visible_field_is_read_as_utc_without_javascript(alice, app):
    make(alice, expires_at="2099-12-31T08:00")
    assert link_row(app).expires_at.hour == 8


def test_cached_schedule_is_respected(alice, redis_fake):
    make(alice, starts_at_utc=iso(timedelta(days=1)))
    assert alice.get("/alice/lnk").status_code == 403
    assert alice.get("/alice/lnk").status_code == 403  # served from cache this time


# ---------- passwords ----------

def test_password_gate_hides_destination(alice, app):
    make(alice, link_password="open-sesame")
    r = alice.get("/alice/lnk")
    assert r.status_code == 200 and 'type="password"' in r.text
    assert URL not in r.text and "location" not in r.headers
    assert click_total(app) == 0  # looking at the form is not a click


def test_correct_password_redirects_and_counts_click(alice, app):
    make(alice, link_password="open-sesame")
    r = alice.post("/alice/lnk", data={"password": "open-sesame"})
    assert r.status_code == 302 and r.headers["location"] == URL
    assert click_total(app) == 1


def test_wrong_password_is_refused(alice, app):
    make(alice, link_password="open-sesame")
    r = alice.post("/alice/lnk", data={"password": "nope-nope"})
    assert r.status_code == 403 and "Wrong password" in r.text
    assert "location" not in r.headers and click_total(app) == 0


def test_password_is_stored_hashed(alice, app):
    make(alice, link_password="open-sesame")
    stored = link_row(app).password_hash
    assert stored.startswith("$2") and "open-sesame" not in stored


def test_password_guessing_is_limited(alice):
    make(alice, link_password="open-sesame")
    codes = [
        alice.post("/alice/lnk", data={"password": f"guess-{i}"}).status_code for i in range(7)
    ]
    assert codes[:5] == [403] * 5 and codes[5:] == [429, 429]
    # even the right password is refused while locked out
    assert alice.post("/alice/lnk", data={"password": "open-sesame"}).status_code == 429


def test_cache_never_leaks_a_protected_link(alice, redis_fake):
    make(alice, link_password="open-sesame")
    for _ in range(2):  # second request comes from the cache
        r = alice.get("/alice/lnk")
        assert r.status_code == 200 and "location" not in r.headers
    cached = redis_fake.get("link:alice:lnk")
    assert '"locked": true' in cached
    assert "$2" not in cached  # no password hash in Redis


def test_short_password_rejected_on_create(alice):
    make(alice, link_password="abc")
    assert alice.get("/alice/lnk").status_code == 404


def test_post_to_open_link_just_redirects_to_get(alice):
    make(alice)
    r = alice.post("/alice/lnk", data={"password": "x"})
    assert r.status_code == 303 and r.headers["location"] == "/alice/lnk"


def test_expired_protected_link_gives_410_before_password(alice, app):
    make(alice, link_password="open-sesame", expires_at_utc=iso(timedelta(hours=1)))
    with app.state.session_factory() as db:
        db.query(Link).one().expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    assert alice.get("/alice/lnk").status_code == 410
    assert alice.post("/alice/lnk", data={"password": "open-sesame"}).status_code == 410


# ---------- managing a link ----------

def edit(client, link_id=1, **fields):
    data = {"original_url": URL, "password_action": "keep", **fields}
    return client.post(f"/dashboard/links/{link_id}/edit", data=data)


def test_edit_page_shows_current_settings(alice):
    make(alice, link_password="open-sesame", starts_at_utc="2099-01-02T03:04:00Z")
    page = alice.get("/dashboard/links/1/edit")
    assert page.status_code == 200
    assert "password protected" in page.text
    assert 'value="2099-01-02T03:04"' in page.text


def test_edit_destination_updates_redirect_and_cache(alice, redis_fake):
    make(alice)
    assert alice.get("/alice/lnk").headers["location"] == URL
    assert redis_fake.get("link:alice:lnk")
    edit(alice, original_url="https://new.example.org/")
    assert redis_fake.get("link:alice:lnk") is None
    assert alice.get("/alice/lnk").headers["location"] == "https://new.example.org/"


def test_add_change_and_remove_password(alice):
    make(alice)
    assert alice.get("/alice/lnk").status_code == 302

    edit(alice, password_action="set", new_password="first-pass")
    assert alice.get("/alice/lnk").status_code == 200
    assert alice.post("/alice/lnk", data={"password": "first-pass"}).status_code == 302

    edit(alice, password_action="set", new_password="second-pass")
    assert alice.post("/alice/lnk", data={"password": "first-pass"}).status_code == 403
    assert alice.post("/alice/lnk", data={"password": "second-pass"}).status_code == 302

    edit(alice, password_action="keep")  # saving other changes keeps it
    assert alice.get("/alice/lnk").status_code == 200

    edit(alice, password_action="remove")
    assert alice.get("/alice/lnk").status_code == 302


def test_cache_cleared_when_password_added(alice, redis_fake):
    make(alice)
    alice.get("/alice/lnk")  # caches it as an open link
    edit(alice, password_action="set", new_password="first-pass")
    assert alice.get("/alice/lnk").status_code == 200  # gate shows immediately


def test_edit_schedule_and_clear_it(alice, app):
    make(alice, expires_at_utc=iso(timedelta(days=5)))
    edit(alice, starts_at_utc=iso(timedelta(days=1)), expires_at_utc=iso(timedelta(days=9)))
    assert alice.get("/alice/lnk").status_code == 403
    edit(alice)  # empty fields remove the schedule
    row = link_row(app)
    assert row.starts_at is None and row.expires_at is None
    assert alice.get("/alice/lnk").status_code == 302


def test_edit_can_expire_a_link_now(alice):
    make(alice)
    edit(alice, expires_at_utc=iso(-timedelta(minutes=1)))
    assert alice.get("/alice/lnk").status_code == 410


def test_edit_validation_keeps_old_settings(alice, app):
    make(alice, link_password="open-sesame")
    edit(alice, original_url="javascript:alert(1)")
    edit(alice, password_action="set", new_password="x")
    edit(alice, password_action="explode")
    edit(alice, starts_at_utc=iso(timedelta(days=2)), expires_at_utc=iso(timedelta(days=1)))
    row = link_row(app)
    assert row.original_url == URL and row.starts_at is None
    assert alice.post("/alice/lnk", data={"password": "open-sesame"}).status_code == 302


def test_cannot_edit_someone_elses_link(alice, make_client):
    from tests.conftest import register

    bob = make_client()
    register(bob, "bob")
    make(bob, "bobs")
    assert alice.get("/dashboard/links/1/edit").status_code == 404
    r = edit(alice, original_url="https://evil.example.org/")
    assert r.status_code == 404
    assert bob.get("/bob/bobs").headers["location"] == URL


def test_edit_requires_login(client):
    assert client.get("/dashboard/links/1/edit").status_code == 303
    assert client.post("/dashboard/links/1/edit", data={"original_url": URL}).status_code == 303


# ---------- dashboard, detail page, export ----------

def test_dashboard_shows_status_and_lock(alice, app):
    make(alice, "open1")
    make(alice, "soon1", starts_at_utc=iso(timedelta(days=2)))
    make(alice, "lock1", link_password="open-sesame")
    make(alice, "old1", expires_at_utc=iso(timedelta(days=1)))
    with app.state.session_factory() as db:
        db.query(Link).filter_by(slug="old1").one().expires_at = utcnow() - timedelta(hours=1)
        db.commit()
    page = alice.get("/dashboard").text
    for label in ("tag ok", "tag warn", "tag bad", "tag lock", "Scheduled", "Expired", "Password"):
        assert label in page
    assert 'data-utc="' in page and "/edit" in page


def test_detail_page_shows_status_and_edit_button(alice):
    make(alice, link_password="open-sesame")
    page = alice.get("/dashboard/links/1").text
    assert "Password protected" in page and "/dashboard/links/1/edit" in page


def test_csv_has_schedule_and_password_columns(alice):
    make(alice, "csv1", link_password="open-sesame", starts_at_utc="2099-01-01T00:00:00Z")
    make(alice, "csv2")
    text = alice.get("/dashboard/links/export.csv").text
    rows = {r["slug"]: r for r in csv.DictReader(io.StringIO(text))}
    assert rows["csv1"]["password_protected"] == "yes"
    assert rows["csv2"]["password_protected"] == "no"
    assert rows["csv1"]["starts_at"].startswith("2099-01-01")
    assert rows["csv2"]["starts_at"] == ""


def test_script_is_versioned(client):
    import re
    assert re.search(r'/static/app\.js\?v=[0-9a-f]{10}"', client.get("/login").text)
