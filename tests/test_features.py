"""The paid-plan gate: everything is free today, but each paid-to-be feature already asks."""

import re

import pytest

from app import features
from app.models import Link

ALL = frozenset(features.FEATURES)


def make(client, slug="lnk", **extra):
    return client.post("/dashboard/links", data={
        "original_url": "https://example.com/" + slug, "slug": slug, **extra})


def lid(app, slug="lnk"):
    with app.state.session_factory() as db:
        return db.query(Link).filter_by(slug=slug).one().id


def lock(monkeypatch, *names):
    monkeypatch.setattr(features, "PAID", frozenset(names) if names else ALL)


def test_every_feature_is_free_for_now():
    assert features.PAID == frozenset()
    assert all(features.can(None, name) for name in features.FEATURES)
    assert set(features.FEATURES) == {
        "click_limit", "tags", "archive", "csv_import", "preview", "utm", "qr_style",
        "color_schemes",
    }


def test_the_basics_are_not_on_the_list():
    for basic in ("schedule", "password", "analytics", "qr"):
        assert basic not in features.FEATURES


def test_an_unknown_feature_is_a_bug_not_a_yes():
    with pytest.raises(KeyError):
        features.can(None, "teleport")


def test_a_paid_feature_needs_a_plan(monkeypatch):
    lock(monkeypatch, "tags")
    assert not features.can(None, "tags") and features.can(None, "archive")
    monkeypatch.setattr(features, "has_paid_plan", lambda user: True)
    assert features.can(None, "tags")


def test_require_raises_a_message_for_the_person(monkeypatch):
    features.require(None, "tags")  # free: fine
    lock(monkeypatch)
    with pytest.raises(ValueError, match="paid plan"):
        features.require(None, "tags")


def test_locked_boxes_are_shown_disabled_with_a_note(alice, monkeypatch):
    make(alice, "one")  # the toolbar (with its Archive button) only exists once there are links
    lock(monkeypatch)
    page = alice.get("/dashboard").text
    assert re.search(r'name="click_limit"[^>]*disabled', page)
    assert re.search(r'name="tags"[^>]*disabled', page)
    assert page.count("This feature is part of a paid plan.") >= 3  # two boxes + Archive button
    assert "data-tag-pick" not in page


def test_locked_features_cannot_be_used_by_posting_the_form_directly(alice, app, monkeypatch):
    lock(monkeypatch)
    make(alice, "a", click_limit="5")
    make(alice, "b", tags="work")
    with app.state.session_factory() as db:
        assert db.query(Link).count() == 0  # neither was created
    assert "This feature is part of a paid plan." in alice.get("/dashboard").text
    make(alice, "plain")  # ordinary links are unaffected
    assert lid(app, "plain")


def test_locked_archive_is_refused(alice, app, monkeypatch):
    make(alice, "one")
    lock(monkeypatch, "archive")
    alice.post("/dashboard/links/archive", data={"ids": [lid(app, "one")], "action": "archive"})
    alice.post(f"/dashboard/links/{lid(app, 'one')}/archive", data={"archived": "1"})
    with app.state.session_factory() as db:
        assert db.query(Link).one().archived_at is None
    page = alice.get("/dashboard?view=archived").text  # the archive view is not available either
    assert "No archived links" not in page and "viewtabs" not in page


def test_the_edit_page_of_a_locked_account_is_read_only_for_these_boxes(alice, app, monkeypatch):
    make(alice, "one", click_limit="4", tags="work")
    lock(monkeypatch)
    page = alice.get(f"/dashboard/links/{lid(app, 'one')}/edit").text
    assert re.search(r'name="click_limit"[^>]*disabled', page)
    assert re.search(r'name="tags"[^>]*disabled', page)
    assert 'name="limit_box"' not in page and 'name="tags_box"' not in page
    assert "Archive link" not in page and "paid plan" in page


def test_saving_the_edit_page_when_locked_keeps_what_was_set(alice, app, monkeypatch):
    make(alice, "one", click_limit="4", tags="work")
    link_id = lid(app, "one")
    lock(monkeypatch)
    # what the locked page really posts: the disabled boxes are not sent at all
    r = alice.post(f"/dashboard/links/{link_id}/edit", data={
        "original_url": "https://example.com/changed", "password_action": "keep"})
    assert r.status_code == 303
    with app.state.session_factory() as db:
        link = db.query(Link).one()
        assert link.original_url == "https://example.com/changed"  # the rest still saves
        assert link.click_limit == 4 and [t.name for t in link.tags] == ["work"]


def test_changing_a_locked_setting_by_hand_is_refused(alice, app, monkeypatch):
    make(alice, "one", click_limit="4", tags="work")
    link_id = lid(app, "one")
    lock(monkeypatch)
    alice.post(f"/dashboard/links/{link_id}/edit", data={
        "original_url": "https://example.com/changed", "password_action": "keep",
        "click_limit": "9", "limit_box": "1", "tags": "other", "tags_box": "1"})
    with app.state.session_factory() as db:
        link = db.query(Link).one()
        assert link.click_limit == 4 and [t.name for t in link.tags] == ["work"]
        assert link.original_url != "https://example.com/changed"  # nothing was saved
    assert "paid plan" in alice.get(f"/dashboard/links/{link_id}/edit").text


def test_an_existing_limit_keeps_working_when_the_feature_becomes_paid(alice, app, monkeypatch):
    make(alice, "one", click_limit="1")
    lock(monkeypatch)
    assert alice.get("/alice/one").status_code == 302
    assert alice.get("/alice/one").status_code == 410


def test_the_dashboard_template_helper_matches(alice, monkeypatch):
    assert 'name="click_limit"' in alice.get("/dashboard").text
    lock(monkeypatch, "click_limit")
    page = alice.get("/dashboard").text
    assert re.search(r'name="click_limit"[^>]*disabled', page)
    assert not re.search(r'name="tags"[^>]*disabled', page)  # only the locked one changes
