"""Duplicate a link: a new link with the same destination and settings, and no history."""
import re
from datetime import timedelta

import pytest

from app import features
from app.models import Click, Link, LinkEdit, Tag, User, utcnow

PW = "password123"
PAID = "This feature is part of a paid plan."


def iso(delta):
    return (utcnow() + delta).isoformat()


def make(client, slug="promo", **extra):
    return client.post("/dashboard/links", data={
        "original_url": "https://example.com/" + slug, "slug": slug, **extra})


def row(app, slug):
    with app.state.session_factory() as db:
        link = db.query(Link).filter_by(slug=slug).one()
        list(link.tags)  # load them before the session closes
        db.expunge(link)
        return link


def count(app):
    with app.state.session_factory() as db:
        return db.query(Link).count()


def duplicate(client, link_id):
    return client.post("/dashboard/links/duplicate", data={"ids": [link_id]})


def page(client, url="/dashboard"):
    return client.get(url).text


# ---------- what a copy is ----------

def test_the_copy_has_the_same_destination_under_a_new_short_name(alice, app):
    make(alice, "promo")
    r = duplicate(alice, row(app, "promo").id)
    copy = row(app, "promo-copy")
    assert r.status_code == 303 and r.headers["location"] == f"/dashboard/links/{copy.id}/edit"
    assert copy.original_url == "https://example.com/promo" and copy.id != row(app, "promo").id
    assert copy.click_count == 0 and copy.is_active and copy.archived_at is None
    assert "Link duplicated as promo-copy" in page(alice, r.headers["location"])


def test_every_setting_is_copied(alice, app):
    make(alice, "promo", link_password="open-sesame", click_limit="5", tags="work, sale",
         starts_at_utc=iso(timedelta(days=1)), expires_at_utc=iso(timedelta(days=9)),
         preview="1", preview_message="Hello from me", alert_limit="1", alert_clicks="3",
         alert_expiry="1")
    with app.state.session_factory() as db:
        link = db.query(Link).filter_by(slug="promo").one()
        link.qr_fg, link.qr_bg = "#112233", "#f4f4f8"
        db.commit()
    original = row(app, "promo")
    duplicate(alice, original.id)
    copy = row(app, "promo-copy")
    for field in ("original_url", "starts_at", "expires_at", "password_hash", "click_limit",
                  "preview", "preview_message", "qr_fg", "qr_bg", "alert_limit", "alert_expiry",
                  "alert_clicks"):
        assert getattr(copy, field) == getattr(original, field), field
    assert sorted(t.name for t in copy.tags) == ["sale", "work"]
    assert copy.password_hash                                     # the same password still works


def test_the_copy_of_a_password_link_opens_with_the_same_password(alice, app, make_client):
    make(alice, "secret", link_password="open-sesame")
    duplicate(alice, row(app, "secret").id)
    visitor = make_client()
    r = visitor.post("/alice/secret-copy", data={"password": "open-sesame"})
    assert r.status_code in (302, 303)
    assert visitor.post("/alice/secret-copy", data={"password": "nope-nope"}).status_code != 302


def test_tags_are_shared_not_made_again(alice, app):
    make(alice, "promo", tags="work")
    duplicate(alice, row(app, "promo").id)
    with app.state.session_factory() as db:
        assert db.query(Tag).count() == 1


def test_a_copy_starts_fresh_even_if_the_original_is_used_up_off_or_archived(alice, app,
                                                                              make_client):
    make(alice, "promo", click_limit="1", alert_limit="1")
    make_client().get("/alice/promo")                              # uses the one click
    with app.state.session_factory() as db:
        link = db.query(Link).filter_by(slug="promo").one()
        link.is_active, link.archived_at = False, utcnow()
        link.alert_limit_sent_at = utcnow()
        db.add(LinkEdit(link_id=link.id, old_url="https://old.example/", new_url=link.original_url))
        db.commit()
        assert db.query(Click).count() == 1
    duplicate(alice, row(app, "promo").id)
    copy = row(app, "promo-copy")
    assert (copy.click_count, copy.limit_reached_at, copy.is_active, copy.archived_at) \
        == (0, None, True, None)
    assert copy.click_limit == 1 and copy.alert_limit and copy.alert_limit_sent_at is None
    with app.state.session_factory() as db:
        assert db.query(Click).filter_by(link_id=copy.id).count() == 0
        assert db.query(LinkEdit).filter_by(link_id=copy.id).count() == 0
    assert make_client().get("/alice/promo-copy").status_code == 302   # and it works


def test_the_original_is_left_exactly_as_it_was(alice, app):
    make(alice, "promo", click_limit="5", tags="work")
    before = row(app, "promo")
    duplicate(alice, before.id)
    after = row(app, "promo")
    assert (after.original_url, after.click_limit, after.click_count, after.slug) \
        == (before.original_url, before.click_limit, before.click_count, before.slug)
    assert [t.name for t in after.tags] == ["work"]


# ---------- names ----------

def test_the_second_copy_is_numbered(alice, app):
    make(alice, "promo")
    link_id = row(app, "promo").id
    duplicate(alice, link_id)
    duplicate(alice, link_id)
    duplicate(alice, row(app, "promo-copy").id)                    # a copy of a copy
    with app.state.session_factory() as db:
        assert {s for (s,) in db.query(Link.slug)} == {
            "promo", "promo-copy", "promo-copy2", "promo-copy-copy"}


def test_a_very_long_name_still_fits(alice, app):
    long_slug = "a" * 32
    make(alice, long_slug)
    duplicate(alice, row(app, long_slug).id)
    with app.state.session_factory() as db:
        slugs = {s for (s,) in db.query(Link.slug)}
    copy = (slugs - {long_slug}).pop()
    assert len(copy) <= 32 and copy.endswith("-copy") and re.fullmatch(r"[A-Za-z0-9_-]+", copy)


def test_when_the_numbered_names_run_out_a_random_one_is_used(alice, app):
    make(alice, "promo")
    with app.state.session_factory() as db:
        user_id = db.query(User).one().id
        names = ["promo-copy"] + [f"promo-copy{n}" for n in range(2, 50)]
        db.add_all(Link(user_id=user_id, slug=n, original_url="https://example.com/x")
                   for n in names)
        db.commit()
    duplicate(alice, row(app, "promo").id)
    with app.state.session_factory() as db:
        fresh = {s for (s,) in db.query(Link.slug)} - set(names) - {"promo"}
    assert len(fresh) == 1 and not next(iter(fresh)).startswith("promo-copy")


# ---------- the two buttons ----------

def test_the_edit_page_button_works(alice, app):
    make(alice, "promo")
    link_id = row(app, "promo").id
    edit_page = page(alice, f"/dashboard/links/{link_id}/edit")
    assert f'action="/dashboard/links/{link_id}/duplicate"' in edit_page
    assert "Duplicate link" in edit_page and "It starts with no clicks." in edit_page
    r = alice.post(f"/dashboard/links/{link_id}/duplicate")
    assert r.status_code == 303 and row(app, "promo-copy")


def test_the_toolbar_button_is_there_and_starts_disabled(alice, app):
    make(alice, "promo")
    html = page(alice)
    button = re.search(r'<button[^>]*id="duplicate-selected"[^>]*>', html).group(0)
    assert 'formaction="/dashboard/links/duplicate"' in button and "disabled" in button
    assert "duplicate.disabled = n !== 1" in html                   # it wakes up for exactly one


def test_the_one_link_buttons_read_edit_analytics_duplicate_share(alice, app):
    make(alice, "promo")
    html = page(alice)
    group = html[html.index('class="selection-actions"'):]
    order = [group.index(f">{word}<") for word in ("Edit", "Analytics", "Duplicate", "Share")]
    assert order == sorted(order)                                   # Share is the last button


@pytest.mark.parametrize("ids", [[], [1, 2]])
def test_the_toolbar_needs_exactly_one_link(alice, app, ids):
    make(alice, "one")
    make(alice, "two")
    r = alice.post("/dashboard/links/duplicate", data={"ids": ids})
    assert r.status_code == 303 and count(app) == 2
    assert "Select exactly one link to duplicate." in page(alice)


def test_the_same_link_ticked_twice_still_counts_as_one(alice, app):
    make(alice, "one")
    link_id = row(app, "one").id
    alice.post("/dashboard/links/duplicate", data={"ids": [link_id, link_id]})
    assert count(app) == 2


# ---------- other people ----------

def test_nobody_can_duplicate_somebody_elses_link(alice, app, make_client):
    make(alice, "mine")
    from tests.conftest import register
    bob = make_client()
    register(bob, "bobby")
    link_id = row(app, "mine").id
    assert bob.post(f"/dashboard/links/{link_id}/duplicate").status_code == 404
    assert bob.post("/dashboard/links/duplicate", data={"ids": [link_id]}).status_code == 404
    assert count(app) == 1


def test_a_logged_out_visitor_is_sent_to_login(alice, app, make_client):
    make(alice, "mine")
    r = make_client().post(f"/dashboard/links/{row(app, 'mine').id}/duplicate")
    assert r.status_code in (303, 401) and count(app) == 1


# ---------- paid features are not smuggled into a free copy ----------

def test_locked_features_are_not_copied(alice, app, monkeypatch):
    make(alice, "promo", click_limit="5", tags="work", preview="1", preview_message="Hi",
         alert_limit="1", alert_clicks="3")
    with app.state.session_factory() as db:
        link = db.query(Link).filter_by(slug="promo").one()
        link.qr_fg, link.qr_bg = "#112233", "#f4f4f8"
        db.commit()
    monkeypatch.setattr(features, "PAID", frozenset(features.FEATURES))
    duplicate(alice, row(app, "promo").id)
    copy = row(app, "promo-copy")
    assert copy.click_limit is None and copy.preview is False and copy.preview_message is None
    assert copy.qr_fg is None and copy.qr_bg is None and copy.tags == []
    assert (copy.alert_limit, copy.alert_expiry, copy.alert_clicks) == (False, False, None)
    assert copy.original_url == "https://example.com/promo"        # the basics always carry over


def test_the_alert_for_the_limit_is_dropped_when_the_limit_is_not_copied(alice, app, monkeypatch):
    make(alice, "promo", click_limit="5", alert_limit="1")
    monkeypatch.setattr(features, "PAID", frozenset({"click_limit"}))
    duplicate(alice, row(app, "promo").id)
    copy = row(app, "promo-copy")
    assert copy.click_limit is None and copy.alert_limit is False   # an alert for nothing


# ---------- limits, languages ----------

def test_making_copies_too_fast_is_stopped(alice, app, redis_fake):
    redis_fake.flushall()
    make(alice, "promo")                                # creating counts too: 30 a minute
    link_id = row(app, "promo").id
    for _ in range(31):
        duplicate(alice, link_id)
    assert count(app) == 30
    assert "creating links too quickly" in page(alice)


def test_the_message_is_translated(alice, app):
    make(alice, "promo")
    alice.cookies.set("lang", "hi")
    r = duplicate(alice, row(app, "promo").id)
    assert "डुप्लिकेट हो गया" in page(alice, r.headers["location"])
