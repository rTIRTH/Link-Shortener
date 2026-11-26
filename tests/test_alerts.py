"""Click alerts by email: the limit is reached, N clicks, or the link is about to end."""
import importlib.util
import re
from datetime import timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app import alerts, features
from app.config import settings
from app.models import Link, User, utcnow
from app.utils import MAX_CLICK_LIMIT

PAID = "This feature is part of a paid plan."


@pytest.fixture()
def mail(alice, monkeypatch):
    """Email on AFTER alice exists; what would be sent is collected as (to, subject, body)."""
    sent = []
    monkeypatch.setattr(settings, "email_backend", "console")
    monkeypatch.setattr(settings, "base_url", "https://short.example")
    monkeypatch.setattr(alerts, "send_email",
                        lambda to, subject, body: sent.append((to, subject, body)) or True)
    return sent


@pytest.fixture()
def visitor(make_client):
    return make_client()


def iso(delta):
    return (utcnow() + delta).isoformat()


def make(client, slug="promo", **extra):
    return client.post("/dashboard/links", data={
        "original_url": "https://example.com/" + slug, "slug": slug, **extra})


def row(app, slug="promo"):
    with app.state.session_factory() as db:
        link = db.query(Link).filter_by(slug=slug).one()
        db.expunge(link)
        return link


def edit(client, link_id, **fields):
    data = {"original_url": "https://example.com/promo", "password_action": "keep", **fields}
    if "click_limit" in fields:
        data["limit_box"] = "1"
    return client.post(f"/dashboard/links/{link_id}/edit", data=data)


def hit(visitor, n=1, slug="promo"):
    return [visitor.get(f"/alice/{slug}").status_code for _ in range(n)]


def flashes(client):
    return client.get("/dashboard").text


def change(app, slug="promo", **values):
    with app.state.session_factory() as db:
        link = db.query(Link).filter_by(slug=slug).one()
        for key, value in values.items():
            setattr(link, key, value)
        db.commit()


# ---------- what the owner types ----------

def test_the_number_box_accepts_whole_numbers_and_native_digits():
    assert alerts.parse_alert_clicks("") is None and alerts.parse_alert_clicks("  ") is None
    assert alerts.parse_alert_clicks("100") == 100
    assert alerts.parse_alert_clicks("1,000") == 1000
    assert alerts.parse_alert_clicks("१००") == 100           # Hindi digits
    assert alerts.parse_alert_clicks("૫૦") == 50             # Gujarati digits
    for bad in ("0", "-3", "abc", "2.5", str(MAX_CLICK_LIMIT + 1)):
        with pytest.raises(ValueError, match="whole number from 1 to 1,000,000"):
            alerts.parse_alert_clicks(bad)


def test_creating_a_link_with_alerts(alice, app, mail):
    make(alice, click_limit="3", alert_limit="1", alert_clicks="2", alert_expiry="1",
         expires_at_utc=iso(timedelta(days=5)))
    link = row(app)
    assert (link.alert_limit, link.alert_expiry, link.alert_clicks) == (True, True, 2)
    assert link.alert_limit_sent_at is None and link.alert_clicks_sent_at is None


def test_a_link_without_alerts_has_them_all_off(alice, app):
    make(alice)
    link = row(app)
    assert (link.alert_limit, link.alert_expiry, link.alert_clicks) == (False, False, None)


@pytest.mark.parametrize("fields,message", [
    ({"alert_limit": "1"}, "Set a click limit first"),
    ({"alert_expiry": "1"}, "Set an end time first"),
    ({"alert_clicks": "abc"}, "whole number from 1 to 1,000,000"),
    ({"alert_clicks": "0"}, "whole number from 1 to 1,000,000"),
])
def test_alerts_that_cannot_work_are_refused_with_a_reason(alice, app, mail, fields, message):
    make(alice, **fields)
    with app.state.session_factory() as db:
        assert db.query(Link).count() == 0
    assert message in flashes(alice)


# ---------- the paid-plan gate and the server without email ----------

def test_a_locked_account_sees_disabled_boxes_and_cannot_post_the_form_by_hand(
        alice, app, mail, monkeypatch):
    monkeypatch.setattr(features, "PAID", frozenset({"alerts"}))
    page = alice.get("/dashboard").text
    assert re.search(r'name="alert_limit"[^>]*disabled', page)
    assert re.search(r'name="alert_clicks"[^>]*disabled', page)
    assert PAID in page
    make(alice, "sneaky", click_limit="2", alert_limit="1")
    make(alice, "also", alert_clicks="5")
    with app.state.session_factory() as db:
        assert db.query(Link).count() == 0
    assert PAID in flashes(alice)
    make(alice, "plain")                                           # ordinary links still work
    assert row(app, "plain")


def test_a_locked_edit_page_keeps_what_was_set_and_refuses_changes(alice, app, mail, monkeypatch):
    make(alice, click_limit="3", alert_limit="1", alert_clicks="2")
    link_id = row(app).id
    monkeypatch.setattr(features, "PAID", frozenset({"alerts"}))
    page = alice.get(f"/dashboard/links/{link_id}/edit").text
    assert 'name="alerts_box"' not in page and PAID in page
    # what the locked page really posts: the disabled boxes are not sent at all
    assert edit(alice, link_id, click_limit="3").status_code == 303
    link = row(app)
    assert (link.alert_limit, link.alert_clicks) == (True, 2)
    # changing it by hand is refused, and nothing else is saved either
    edit(alice, link_id, click_limit="3", alerts_box="1", alert_clicks="9",
         original_url="https://example.com/changed")
    link = row(app)
    assert link.alert_clicks == 2 and link.original_url != "https://example.com/changed"


def test_without_email_the_boxes_say_so_and_nothing_is_ever_sent(alice, app, monkeypatch):
    page = alice.get("/dashboard").text                            # email is off in this test
    assert "which is not set up on this server yet" in page
    assert re.search(r'name="alert_limit"[^>]*disabled', page)
    make(alice, click_limit="1", alert_limit="1")
    link_id = row(app).id
    assert 'name="alerts_box"' not in alice.get(f"/dashboard/links/{link_id}/edit").text
    sent = []
    monkeypatch.setattr(alerts, "send_email", lambda *a: sent.append(a) or True)
    assert alerts.send_due_alerts(app.state.session_factory) == 0
    alerts.after_click(app.state.session_factory, link_id)
    assert sent == [] and row(app).alert_limit_sent_at is None     # nothing sent, nothing used up


def test_the_edit_page_shows_the_choices_as_they_are(alice, app, mail):
    make(alice, click_limit="3", alert_limit="1", alert_clicks="2")
    page = alice.get(f"/dashboard/links/{row(app).id}/edit").text
    assert 'name="alerts_box"' in page
    assert re.search(r'name="alert_limit" value="1" checked', page)
    assert not re.search(r'name="alert_expiry" value="1" checked', page)
    assert re.search(r'name="alert_clicks"[^>]*value="2"', page)


# ---------- editing ----------

def test_editing_changes_the_choices_and_checks_them(alice, app, mail):
    make(alice, click_limit="10", expires_at_utc=iso(timedelta(days=9)))
    link_id = row(app).id
    edit(alice, link_id, click_limit="10", alerts_box="1", alert_limit="1", alert_clicks="4",
         alert_expiry="1", expires_at_utc=iso(timedelta(days=9)))
    link = row(app)
    assert (link.alert_limit, link.alert_expiry, link.alert_clicks) == (True, True, 4)
    # turning them off again
    edit(alice, link_id, click_limit="10", alerts_box="1", expires_at_utc=iso(timedelta(days=9)))
    link = row(app)
    assert (link.alert_limit, link.alert_expiry, link.alert_clicks) == (False, False, None)


def test_the_limit_alert_needs_a_limit_and_the_expiry_alert_an_end(alice, app, mail):
    make(alice, click_limit="5", alert_limit="1")
    link_id = row(app).id
    edit(alice, link_id, click_limit="", alerts_box="1", alert_limit="1")
    assert "Set a click limit first" in flashes(alice)
    assert row(app).click_limit == 5                              # nothing was saved
    edit(alice, link_id, click_limit="5", alerts_box="1", alert_expiry="1")
    assert "Set an end time first" in flashes(alice)


def test_the_milestone_must_be_above_the_clicks_so_far(alice, app, mail, visitor):
    make(alice, alert_clicks="50")
    hit(visitor, 3)
    link_id = row(app).id
    edit(alice, link_id, alerts_box="1", alert_clicks="3")
    assert "higher than the clicks this link already has" in flashes(alice)
    assert row(app).alert_clicks == 50
    edit(alice, link_id, alerts_box="1", alert_clicks="4")
    assert row(app).alert_clicks == 4


def test_a_milestone_already_in_place_is_not_refused_when_saving_something_else(
        alice, app, mail, visitor):
    make(alice, alert_clicks="2")
    hit(visitor, 3)                                                # past the milestone
    assert edit(alice, row(app).id, alerts_box="1", alert_clicks="2").headers["location"] \
        == "/dashboard"
    assert row(app).alert_clicks == 2


def test_changing_a_setting_arms_that_alert_again(alice, app, mail):
    make(alice, click_limit="5", alert_limit="1", alert_clicks="3", alert_expiry="1",
         expires_at_utc=iso(timedelta(days=9)))
    stamp = utcnow()
    change(app, alert_limit_sent_at=stamp, alert_clicks_sent_at=stamp, alert_expiry_sent_at=stamp)
    link_id = row(app).id
    # saving without changing anything keeps what was already sent
    link = row(app)
    edit(alice, link_id, click_limit="5", alerts_box="1", alert_limit="1", alert_clicks="3",
         alert_expiry="1", expires_at_utc=link.expires_at.isoformat())
    link = row(app)
    assert link.alert_limit_sent_at and link.alert_clicks_sent_at and link.alert_expiry_sent_at
    # a new milestone arms only the milestone
    edit(alice, link_id, click_limit="5", alerts_box="1", alert_limit="1", alert_clicks="4",
         alert_expiry="1", expires_at_utc=link.expires_at.isoformat())
    link = row(app)
    assert link.alert_clicks_sent_at is None
    assert link.alert_limit_sent_at and link.alert_expiry_sent_at
    # a new limit arms the limit alert; a new end time arms the expiry alert
    edit(alice, link_id, click_limit="8", alerts_box="1", alert_limit="1", alert_clicks="4",
         alert_expiry="1", expires_at_utc=iso(timedelta(days=12)))
    link = row(app)
    assert link.alert_limit_sent_at is None and link.alert_expiry_sent_at is None


# ---------- the click limit alert ----------

def test_the_owner_is_told_when_the_limit_is_reached(alice, app, mail, visitor):
    make(alice, click_limit="2", alert_limit="1")
    assert hit(visitor, 1) == [302] and mail == []                # one click left: no email yet
    assert hit(visitor, 1) == [302]
    assert len(mail) == 1
    to, subject, body = mail[0]
    link_id = row(app).id
    assert to == "alice@example.com"
    assert subject == "Your link alice/promo has reached its click limit"
    assert "https://short.example/alice/promo" in body and "all 2 of its clicks" in body
    assert f"https://short.example/dashboard/links/{link_id}/edit" in body
    assert row(app).alert_limit_sent_at is not None


def test_each_alert_goes_out_only_once(alice, app, mail, visitor):
    make(alice, click_limit="2", alert_limit="1")
    assert hit(visitor, 4) == [302, 302, 410, 410]                # the 410s are not clicks
    assert len(mail) == 1


def test_links_without_the_alert_send_nothing(alice, app, mail, visitor):
    make(alice, click_limit="1")
    hit(visitor, 2)
    assert mail == []


def test_link_preview_robots_do_not_trigger_alerts(alice, app, mail, visitor):
    make(alice, click_limit="1", alert_limit="1")
    bot = {"user-agent": "Mozilla/5.0 (compatible; Slackbot-LinkExpanding 1.0)"}
    assert visitor.get("/alice/promo", headers=bot).status_code == 302
    assert mail == []                                              # a robot did not use the click


# ---------- the "N clicks" alert ----------

def test_the_owner_is_told_when_a_link_reaches_the_chosen_number_of_clicks(
        alice, app, mail, visitor):
    make(alice, alert_clicks="3")
    hit(visitor, 2)
    assert mail == []
    hit(visitor, 1)
    assert len(mail) == 1
    _to, subject, body = mail[0]
    assert subject == "Your link alice/promo has reached 3 click(s)"
    link_id = row(app).id
    assert f"https://short.example/dashboard/links/{link_id}" in body       # where to see who
    hit(visitor, 5)
    assert len(mail) == 1                                          # still only one


def test_a_new_milestone_can_be_reached_after_the_first(alice, app, mail, visitor):
    make(alice, alert_clicks="2")
    hit(visitor, 2)
    assert len(mail) == 1
    edit(alice, row(app).id, alerts_box="1", alert_clicks="5")
    hit(visitor, 3)
    assert len(mail) == 2 and "reached 5 click(s)" in mail[1][1]


def test_one_email_when_the_milestone_and_the_limit_arrive_together(alice, app, mail, visitor):
    make(alice, click_limit="3", alert_limit="1", alert_clicks="3")
    hit(visitor, 3)
    assert len(mail) == 1 and "click limit" in mail[0][1]
    link = row(app)
    assert link.alert_limit_sent_at and link.alert_clicks_sent_at


# ---------- links that are about to end ----------

def ending(app, alice, slug="promo", hours=3, **extra):
    make(alice, slug, alert_expiry="1", expires_at_utc=iso(timedelta(days=30)), **extra)
    end = (utcnow() + timedelta(hours=hours)).replace(second=0, microsecond=0)
    change(app, slug, expires_at=end)
    return end


def test_a_link_ending_within_a_day_gets_one_email(alice, app, mail):
    end = ending(app, alice)
    assert alerts.send_due_alerts(app.state.session_factory) == 1
    _to, subject, body = mail[0]
    assert subject == "Your link alice/promo ends soon"
    assert end.strftime("%H:%M") in body and "UTC" in body and str(end.year) in body
    assert "https://short.example/alice/promo" in body
    assert alerts.send_due_alerts(app.state.session_factory) == 0   # not again
    assert len(mail) == 1


def test_links_that_end_later_or_have_ended_or_are_off_get_nothing(alice, app, mail):
    ending(app, alice, "later", hours=30)
    ending(app, alice, "over", hours=-2)
    ending(app, alice, "off", hours=3)
    change(app, "off", is_active=False)
    make(alice, "quiet", expires_at_utc=iso(timedelta(hours=3)))   # ends soon, but no alert asked
    assert alerts.send_due_alerts(app.state.session_factory) == 0
    assert mail == []


def test_moving_the_end_time_arms_the_alert_again(alice, app, mail):
    ending(app, alice)
    alerts.send_due_alerts(app.state.session_factory)
    link_id = row(app).id
    edit(alice, link_id, alerts_box="1", alert_expiry="1", expires_at_utc=iso(timedelta(hours=5)))
    assert alerts.send_due_alerts(app.state.session_factory) == 1
    assert len(mail) == 2


def test_the_sweep_sends_limit_emails_that_could_not_go_out_the_first_time(
        alice, app, mail, visitor, monkeypatch):
    monkeypatch.setattr(alerts, "send_email", lambda *a: False)    # the provider is down
    make(alice, click_limit="2", alert_limit="1")
    hit(visitor, 2)
    assert row(app).alert_limit_sent_at is None                    # the claim was given back
    monkeypatch.setattr(alerts, "send_email",
                        lambda to, subject, body: mail.append((to, subject, body)) or True)
    assert alerts.send_due_alerts(app.state.session_factory) == 1
    assert len(mail) == 1 and "click limit" in mail[0][1]


# ---------- when the sweep runs ----------

def test_opening_the_dashboard_sends_the_emails_that_are_due(alice, app, mail):
    ending(app, alice)
    alice.get("/dashboard")                                        # runs after the page is sent
    assert len(mail) == 1


def test_a_click_on_any_link_also_sends_them(alice, app, mail, visitor):
    ending(app, alice, "soon")
    make(alice, "busy")
    visitor.get("/alice/busy")
    assert len(mail) == 1 and "ends soon" in mail[0][1]


def test_the_sweep_runs_at_most_every_ten_minutes(app, monkeypatch):
    runs = []
    monkeypatch.setattr(settings, "email_backend", "console")
    monkeypatch.setattr(alerts, "send_due_alerts", lambda factory, site="": runs.append(1) or 0)
    for _ in range(5):
        alerts.maybe_sweep(app.state.session_factory)
    assert runs == [1]


def test_the_throttle_also_works_with_redis(app, redis_fake, monkeypatch):
    runs = []
    monkeypatch.setattr(settings, "email_backend", "console")
    monkeypatch.setattr(alerts, "send_due_alerts", lambda factory, site="": runs.append(1) or 0)
    alerts.maybe_sweep(app.state.session_factory)
    alerts.maybe_sweep(app.state.session_factory)
    assert runs == [1] and 0 < redis_fake.ttl("alerts:sweep") <= alerts.SWEEP_EVERY_SECONDS


def test_a_failing_sweep_never_breaks_the_page(alice, app, mail, monkeypatch):
    def boom(factory, site=""):
        raise RuntimeError("the database blinked")
    monkeypatch.setattr(alerts, "send_due_alerts", boom)
    assert alice.get("/dashboard").status_code == 200


# ---------- the cron address ----------

def test_run_alerts_does_not_exist_without_a_secret(alice, mail, monkeypatch):
    monkeypatch.setattr(settings, "cron_secret", "")
    assert alice.get("/run-alerts").status_code == 404
    assert alice.get("/run-alerts?key=").status_code == 404


def test_run_alerts_needs_the_right_key(alice, app, mail, visitor, monkeypatch):
    monkeypatch.setattr(settings, "cron_secret", "a-long-secret-value")
    ending(app, alice)
    assert visitor.get("/run-alerts").status_code == 404
    assert visitor.get("/run-alerts?key=wrong").status_code == 404
    assert mail == []
    r = visitor.get("/run-alerts?key=a-long-secret-value")
    assert r.status_code == 200 and r.json() == {"sent": 1}
    assert visitor.post("/run-alerts?key=a-long-secret-value").json() == {"sent": 0}


def test_run_alerts_also_takes_the_key_as_a_bearer_header(alice, app, mail, visitor, monkeypatch):
    monkeypatch.setattr(settings, "cron_secret", "a-long-secret-value")
    ending(app, alice)
    r = visitor.get("/run-alerts", headers={"Authorization": "Bearer a-long-secret-value"})
    assert r.json() == {"sent": 1}


def test_the_address_is_not_a_username_or_a_short_link(alice, visitor):
    assert visitor.get("/run-alerts").status_code == 404           # "not found", not a crash


# ---------- limits on how many emails go out ----------

def test_one_person_gets_at_most_so_many_alert_emails_a_day(alice, app, mail, visitor, monkeypatch):
    monkeypatch.setattr(settings, "alert_user_daily_limit", 1)
    make(alice, "one", click_limit="1", alert_limit="1")
    make(alice, "two", click_limit="1", alert_limit="1")
    hit(visitor, 1, "one")
    hit(visitor, 1, "two")
    assert len(mail) == 1
    assert row(app, "two").alert_limit_sent_at is None             # it stays waiting, not lost


def test_the_whole_site_has_a_daily_budget_too(alice, app, mail, visitor, monkeypatch):
    monkeypatch.setattr(settings, "alert_email_daily_limit", 1)
    make(alice, "one", click_limit="1", alert_limit="1")
    make(alice, "two", click_limit="1", alert_limit="1")
    hit(visitor, 1, "one")
    hit(visitor, 1, "two")
    assert len(mail) == 1


def test_two_workers_cannot_both_claim_the_same_alert(alice, app, mail):
    make(alice, click_limit="1", alert_limit="1")
    link_id = row(app).id
    with app.state.session_factory() as one, app.state.session_factory() as two:
        assert alerts._claim(one, link_id, "limit") is True
        assert alerts._claim(two, link_id, "limit") is False


# ---------- what the email says ----------

def test_the_email_follows_the_owners_language(alice, app, mail, visitor):
    with app.state.session_factory() as db:
        db.query(User).filter_by(username="alice").one().language = "hi"
        db.commit()
    make(alice, click_limit="2", alert_limit="1")
    hit(visitor, 2)
    _to, subject, body = mail[0]
    assert subject == "आपके लिंक alice/promo की क्लिक सीमा पूरी हो गई"
    assert "२" in body                                  # the limit, in Hindi digits
    assert "https://short.example/alice/promo" in body


def test_the_expiry_email_writes_the_time_in_gujarati_digits(alice, app, mail):
    with app.state.session_factory() as db:
        db.query(User).filter_by(username="alice").one().language = "gu"
        db.commit()
    end = ending(app, alice)
    alerts.send_due_alerts(app.state.session_factory)
    body = mail[0][2]
    assert end.strftime("%H:%M") not in body and "UTC" in body
    assert any("\u0AE6" <= ch <= "\u0AEF" for ch in body)


def test_the_address_in_the_email_comes_from_the_server_not_the_host_header(
        alice, app, mail, visitor):
    make(alice, click_limit="1", alert_limit="1")
    visitor.get("/alice/promo", headers={"host": "evil.example"})
    assert "evil" not in mail[0][2] and "https://short.example/" in mail[0][2]


# ---------- the database ----------

def test_the_migration_adds_the_columns_and_takes_them_away_again():
    spec = importlib.util.spec_from_file_location(
        "m0014", Path("alembic/versions/0014_click_alerts.py"))
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "0014" and migration.down_revision == "0013"

    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE links (id INTEGER PRIMARY KEY, slug VARCHAR(32))"))
        conn.execute(sa.text("INSERT INTO links (slug) VALUES ('old')"))
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
        cols = {c["name"] for c in sa.inspect(conn).get_columns("links")}
        assert cols - {"id", "slug"} == {
            "alert_limit", "alert_expiry", "alert_clicks", "alert_limit_sent_at",
            "alert_expiry_sent_at", "alert_clicks_sent_at"}
        # a link that existed before has every alert off
        assert conn.execute(sa.text(
            "SELECT alert_limit, alert_expiry, alert_clicks FROM links")).one() == (0, 0, None)
        with Operations.context(MigrationContext.configure(conn)):
            migration.downgrade()
        assert {c["name"] for c in sa.inspect(conn).get_columns("links")} == {"id", "slug"}


def test_the_model_matches_the_migration():
    text = Path("alembic/versions/0014_click_alerts.py").read_text(encoding="utf-8")
    for name in ("alert_limit", "alert_expiry", "alert_clicks", "alert_limit_sent_at",
                 "alert_expiry_sent_at", "alert_clicks_sent_at"):
        assert hasattr(Link, name) and f"'{name}'" in text
