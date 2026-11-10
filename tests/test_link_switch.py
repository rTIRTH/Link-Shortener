"""The owner's on/off switch for a link (Deactivate / Activate button on the edit page)."""

import csv
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.activity import day_state, link_events
from app.config import settings
from app.models import Click, Link, LinkToggle

URL = "https://example.com/page"


def make(client, slug="lnk", **fields):
    return client.post("/dashboard/links", data={"original_url": URL, "slug": slug, **fields})


def link_id(app, slug="lnk"):
    with app.state.session_factory() as db:
        return db.query(Link).filter_by(slug=slug).one().id


def switch(client, app, on: bool, slug="lnk"):
    return client.post(f"/dashboard/links/{link_id(app, slug)}/toggle",
                       data={"active": "1" if on else "0"})


def clicks(app):
    with app.state.session_factory() as db:
        return db.query(Click).count()


# ---- the button on the edit page ------------------------------------------------------------


def test_new_links_are_on_and_the_edit_page_offers_deactivate(alice, app):
    make(alice)
    with app.state.session_factory() as db:
        assert db.query(Link).one().is_active is True
    page = alice.get(f"/dashboard/links/{link_id(app)}/edit").text
    assert "Deactivate link" in page and "Activate link" not in page
    assert 'name="active" value="0"' in page and f"/dashboard/links/{link_id(app)}/toggle" in page


def test_deactivating_stops_the_redirect_and_activating_restores_it(alice, app):
    make(alice)
    edit = f"/dashboard/links/{link_id(app)}/edit"
    assert alice.get("/alice/lnk").status_code == 302
    r = switch(alice, app, False)
    assert r.status_code == 303 and r.headers["location"] == edit

    page = alice.get(edit).text  # where the browser lands after the click
    assert "Link deactivated." in page
    assert "Activate link" in page and "Deactivate link" not in page

    off = alice.get("/alice/lnk")
    assert off.status_code == 403 and "location" not in off.headers
    assert "This short link is turned off." in off.text and URL not in off.text
    assert clicks(app) == 1  # the visit while it was off is not counted

    switch(alice, app, True)
    assert "Link activated." in alice.get(edit).text
    assert alice.get("/alice/lnk").status_code == 302


def test_the_change_is_instant_even_when_the_link_was_cached(alice, app, redis_fake):
    make(alice)
    assert alice.get("/alice/lnk").status_code == 302  # now cached in Redis
    assert redis_fake.keys("link:*")
    switch(alice, app, False)
    assert alice.get("/alice/lnk").status_code == 403
    switch(alice, app, True)
    assert alice.get("/alice/lnk").status_code == 302


def test_a_deactivated_password_link_cannot_be_unlocked(alice, app):
    make(alice, link_password="open-sesame")
    switch(alice, app, False)
    assert alice.get("/alice/lnk").status_code == 403
    r = alice.post("/alice/lnk", data={"password": "open-sesame"})
    assert r.status_code == 403 and "location" not in r.headers and clicks(app) == 0


def test_switch_is_independent_of_the_schedule(alice, app):
    make(alice, ends_at_utc="2099-01-01T00:00:00Z", expires_at_utc="2099-01-01T00:00:00Z")
    switch(alice, app, False)
    assert alice.get("/alice/lnk").status_code == 403
    switch(alice, app, True)
    assert alice.get("/alice/lnk").status_code == 302


def test_repeating_or_garbage_changes_nothing(alice, app):
    make(alice)
    switch(alice, app, False)
    switch(alice, app, False)  # a double click
    alice.post(f"/dashboard/links/{link_id(app)}/toggle", data={"active": "banana"})
    with app.state.session_factory() as db:
        assert db.query(Link).one().is_active is False
        assert db.query(LinkToggle).count() == 1


def test_only_the_owner_can_switch_a_link(alice, app, make_client):
    make(alice)
    bob = make_client()
    bob.post("/register", data={"username": "bob", "email": "bob@example.com",
                                "password": "password123"})
    r = bob.post(f"/dashboard/links/{link_id(app)}/toggle", data={"active": "0"})
    assert r.status_code == 404
    assert alice.get("/alice/lnk").status_code == 302
    anonymous = make_client()
    assert anonymous.post(f"/dashboard/links/{link_id(app)}/toggle",
                          data={"active": "0"}).status_code in (303, 401)


def test_saving_the_edit_form_keeps_the_switch(alice, app):
    make(alice)
    switch(alice, app, False)
    alice.post(f"/dashboard/links/{link_id(app)}/edit",
               data={"original_url": "https://new.example.org/"})
    with app.state.session_factory() as db:
        assert db.query(Link).one().is_active is False
    assert alice.get("/alice/lnk").status_code == 403


# ---- dashboard, stats and export ------------------------------------------------------------


def test_dashboard_and_stats_show_inactive(alice, app):
    make(alice)
    switch(alice, app, False)
    dash = alice.get("/dashboard").text
    assert '<span class="tag off">Inactive</span>' in dash
    stats = alice.get(f"/dashboard/links/{link_id(app)}").text
    assert '<span class="tag off">Inactive</span>' in stats
    assert "Deactivated" in stats  # in the activity log's timeline
    assert "Right now this link is" in alice.get(f"/dashboard/links/{link_id(app)}/edit").text


def test_csv_has_an_active_column(alice, app):
    make(alice, "on1")
    make(alice, "off1")
    switch(alice, app, False, "off1")
    rows = {r["slug"]: r for r in csv.DictReader(io.StringIO(
        alice.get("/dashboard/links/export.csv").text))}
    assert rows["on1"]["active"] == "yes" and rows["off1"]["active"] == "no"


@pytest.mark.parametrize("lang", ["hi", "gu"])
def test_switch_texts_are_translated(alice, app, lang):
    make(alice)
    alice.post("/language", data={"lang": lang, "next": "/"})
    edit = f"/dashboard/links/{link_id(app)}/edit"
    assert "Deactivate link" not in alice.get(edit).text
    switch(alice, app, False)
    assert "Link deactivated." not in alice.get(edit).text
    assert "Activate link" not in alice.get(edit).text
    assert "turned off" not in alice.get("/alice/lnk").text


# ---- the activity log understands the switch ------------------------------------------------

NOW = datetime(2026, 11, 9, 18, 0, tzinfo=timezone.utc)
TODAY, YESTERDAY = NOW.date(), NOW.date() - timedelta(days=1)


class Row:  # a stand-in for Link / LinkToggle, so no database is needed
    def __init__(self, **kw):
        self.__dict__.update(kw)


def link(**kw):
    base = {"created_at": NOW - timedelta(days=5), "starts_at": None, "expires_at": None}
    return Row(**{**base, **kw})


def off(at):
    return Row(at=at, active=False)


def on(at):
    return Row(at=at, active=True)


def test_a_day_switched_off_all_day_is_inactive():
    toggles = [off(NOW - timedelta(days=2))]
    assert day_state(link(), TODAY, timezone.utc, NOW, toggles) == "inactive"
    assert day_state(link(), YESTERDAY, timezone.utc, NOW, toggles) == "inactive"


def test_switched_off_during_the_day_is_partial():
    toggles = [off(datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc))]
    assert day_state(link(), TODAY, timezone.utc, NOW, toggles) == "partial"
    assert day_state(link(), YESTERDAY, timezone.utc, NOW, toggles) == "active"


def test_off_then_on_again():
    toggles = [off(datetime(2026, 11, 8, 6, 0, tzinfo=timezone.utc)),
               on(datetime(2026, 11, 9, 6, 0, tzinfo=timezone.utc))]
    assert day_state(link(), YESTERDAY, timezone.utc, NOW, toggles) == "partial"
    assert day_state(link(), TODAY, timezone.utc, NOW, toggles) == "partial"
    assert day_state(link(), TODAY - timedelta(days=2), timezone.utc, NOW, toggles) == "active"


def test_off_and_on_in_the_wrong_order_still_make_sense():
    toggles = [on(NOW - timedelta(hours=1)), off(NOW - timedelta(days=3))]  # unsorted input
    assert day_state(link(), TODAY - timedelta(days=2), timezone.utc, NOW, toggles) == "inactive"


def test_the_schedule_still_wins_for_closed_days():
    toggles = [off(NOW - timedelta(days=4))]
    gone = link(expires_at=NOW - timedelta(days=3))
    assert day_state(gone, TODAY, timezone.utc, NOW, toggles) == "expired"
    later = link(starts_at=NOW + timedelta(days=1))
    assert day_state(later, TODAY, timezone.utc, NOW, toggles) == "scheduled"


def test_events_list_the_switches_in_order_and_keep_only_the_latest_ten():
    toggles = []
    for i in range(30):
        toggles.append(Row(at=NOW - timedelta(days=4, hours=-i), active=bool(i % 2)))
    events = link_events(link(), NOW, toggles)
    keys = [e["key"] for e in events]
    assert keys[0] == "created" and len(events) == 11
    assert [e["at"] for e in events] == sorted(e["at"] for e in events)
    assert set(keys[1:]) == {"on", "off"}


# ---- the database migration -----------------------------------------------------------------


def test_the_migration_keeps_existing_links_switched_on(tmp_path, monkeypatch):
    from alembic.config import Config
    from sqlalchemy import create_engine, text

    from alembic import command

    root = Path(__file__).resolve().parent.parent
    url = f"sqlite:///{tmp_path / 'old.db'}"
    monkeypatch.setattr(settings, "database_url", url)
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("path_separator", "os")

    command.upgrade(config, "0007")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (username, email, password_hash, created_at) "
                          "VALUES ('old', 'old@example.com', 'x', '2026-01-02 03:04:05')"))
        conn.execute(text("INSERT INTO links (user_id, slug, original_url, created_at, "
                          "click_count) VALUES (1, 'a', 'https://example.com', "
                          "'2026-01-02 03:04:05', 0)"))
    command.upgrade(config, "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT is_active FROM links")).scalar() in (1, True)
        assert conn.execute(text("SELECT count(*) FROM link_toggles")).scalar() == 0
    command.downgrade(config, "0007")  # and it can be undone
    command.upgrade(config, "head")


def test_deleting_a_link_removes_its_switch_history(alice, app):
    make(alice)
    switch(alice, app, False)
    alice.post(f"/dashboard/links/{link_id(app)}/delete")
    with app.state.session_factory() as db:
        assert db.query(Link).count() == 0 and db.query(LinkToggle).count() == 0
