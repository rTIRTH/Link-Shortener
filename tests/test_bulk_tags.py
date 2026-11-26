"""Tag selected: put tags on several links at once, or take them off again."""
import re
from pathlib import Path

import pytest

from app import features
from app.models import Link, Tag, User
from tests.conftest import register

PAID = "This feature is part of a paid plan."


def make(client, slug, **extra):
    return client.post("/dashboard/links", data={
        "original_url": "https://example.com/" + slug, "slug": slug, **extra})


def link_id(app, slug):
    with app.state.session_factory() as db:
        return db.query(Link).filter_by(slug=slug).one().id


def tags_of(app, slug):
    with app.state.session_factory() as db:
        return sorted(t.name for t in db.query(Link).filter_by(slug=slug).one().tags)


def all_tags(app):
    with app.state.session_factory() as db:
        return sorted(t.name for t in db.query(Tag))


def tag(client, app, slugs, names, action="add"):
    return client.post("/dashboard/links/tags", data={
        "ids": [link_id(app, s) for s in slugs], "bulk_tags": names, "action": action})


def said(client):
    return client.get("/dashboard").text


@pytest.fixture()
def three(alice, app):
    for slug in ("one", "two", "three"):
        make(alice, slug)
    return alice


# ---------- adding ----------

def test_tags_go_onto_every_selected_link_and_only_those(three, app):
    r = tag(three, app, ["one", "two"], "work, sale")
    assert r.status_code == 303 and r.headers["location"] == "/dashboard"
    assert tags_of(app, "one") == ["sale", "work"] == tags_of(app, "two")
    assert tags_of(app, "three") == []
    assert "Tags added to 2 link(s)." in said(three)


def test_each_tag_exists_once_however_many_links_have_it(three, app):
    tag(three, app, ["one", "two", "three"], "work")
    assert all_tags(app) == ["work"]


def test_links_keep_the_tags_they_already_had(three, app):
    make(three, "four", tags="old")
    tag(three, app, ["four", "one"], "new")
    assert tags_of(app, "four") == ["new", "old"] and tags_of(app, "one") == ["new"]


def test_adding_a_tag_a_link_already_has_changes_nothing(three, app):
    tag(three, app, ["one"], "work")
    tag(three, app, ["one", "two"], "work")
    assert tags_of(app, "one") == ["work"] == tags_of(app, "two")
    assert all_tags(app) == ["work"]


def test_names_are_cleaned_like_everywhere_else(three, app):
    tag(three, app, ["one"], "  Work ,  SALE  ")
    assert tags_of(app, "one") == ["sale", "work"]


def test_archived_links_can_be_tagged_too(three, app):
    three.post("/dashboard/links/archive", data={"ids": [link_id(app, "one")], "action": "archive"})
    tag(three, app, ["one"], "later")
    assert tags_of(app, "one") == ["later"]


def test_a_full_link_is_skipped_and_the_others_are_tagged(three, app):
    make(three, "full", tags="a, b, c, d, e")
    tag(three, app, ["full", "one"], "extra")
    assert tags_of(app, "full") == ["a", "b", "c", "d", "e"]
    assert tags_of(app, "one") == ["extra"]
    page = said(three)
    assert "Tags added to 1 link(s)." in page
    assert "1 link(s) already have 5 tags, so they were skipped." in page


def test_when_every_link_is_full_only_the_warning_shows(three, app):
    make(three, "full", tags="a, b, c, d, e")
    tag(three, app, ["full"], "extra")
    page = said(three)
    assert "already have 5 tags" in page and "Tags added to" not in page


def test_a_link_with_four_tags_takes_one_more_but_not_two(three, app):
    make(three, "four", tags="a, b, c, d")
    tag(three, app, ["four"], "e")
    assert tags_of(app, "four") == ["a", "b", "c", "d", "e"]
    make(three, "four2", tags="a, b, c, d")
    tag(three, app, ["four2"], "x, y")
    assert tags_of(app, "four2") == ["a", "b", "c", "d"]


# ---------- removing ----------

def test_tags_come_off_the_selected_links_only(three, app):
    tag(three, app, ["one", "two", "three"], "work, sale")
    tag(three, app, ["one", "two"], "work", action="remove")
    assert tags_of(app, "one") == ["sale"] == tags_of(app, "two")
    assert tags_of(app, "three") == ["sale", "work"]
    assert "Tags removed from 2 link(s)." in said(three)


def test_a_tag_nobody_uses_any_more_disappears(three, app):
    tag(three, app, ["one", "two"], "work, sale")
    tag(three, app, ["one", "two"], "sale", action="remove")
    assert all_tags(app) == ["work"]


def test_removing_a_tag_a_link_does_not_have_is_harmless(three, app):
    tag(three, app, ["one"], "work")
    assert tag(three, app, ["one", "two"], "other", action="remove").status_code == 303
    assert tags_of(app, "one") == ["work"]


# ---------- mistakes ----------

def test_nothing_selected(three, app):
    r = three.post("/dashboard/links/tags", data={"bulk_tags": "work", "action": "add"})
    assert r.status_code == 303 and all_tags(app) == []
    assert "Select at least one link first." in said(three)


def test_nothing_typed(three, app):
    for names in ("", " , ,"):
        tag(three, app, ["one"], names)
        assert "Type at least one tag first." in said(three)
    assert all_tags(app) == []


def test_six_tags_at_once_are_refused(three, app):
    tag(three, app, ["one"], "a, b, c, d, e, f")
    assert "A link can have up to 5 tags." in said(three)
    assert all_tags(app) == []


def test_the_tag_limit_for_a_whole_account_is_respected_and_nothing_half_happens(three, app):
    with app.state.session_factory() as db:
        user_id = db.query(User).one().id
        db.add_all(Tag(user_id=user_id, name=f"t{n}") for n in range(50))
        db.commit()
    tag(three, app, ["one", "two"], "brand-new")
    assert "You can have up to 50 tags in total." in said(three)
    assert tags_of(app, "one") == [] == tags_of(app, "two") and "brand-new" not in all_tags(app)


def test_an_unknown_action_just_adds(three, app):
    tag(three, app, ["one"], "work", action="whatever")
    assert tags_of(app, "one") == ["work"]


# ---------- other people ----------

def test_somebody_elses_links_are_never_touched(three, app, make_client):
    bob = make_client()
    register(bob, "bobby")
    make(bob, "bobs")
    mine, his = link_id(app, "one"), link_id(app, "bobs")
    three.post("/dashboard/links/tags", data={"ids": [mine, his], "bulk_tags": "mine",
                                              "action": "add"})
    assert tags_of(app, "one") == ["mine"] and tags_of(app, "bobs") == []
    bob.post("/dashboard/links/tags", data={"ids": [his], "bulk_tags": "x", "action": "add"})
    three.post("/dashboard/links/tags", data={"ids": [his], "bulk_tags": "x", "action": "remove"})
    assert tags_of(app, "bobs") == ["x"]


def test_a_logged_out_visitor_cannot_use_it(three, app, make_client):
    r = make_client().post("/dashboard/links/tags", data={
        "ids": [link_id(app, "one")], "bulk_tags": "x", "action": "add"})
    assert r.status_code in (303, 401) and all_tags(app) == []


# ---------- the paid-plan gate ----------

def test_a_locked_account_cannot_post_it_by_hand(three, app, monkeypatch):
    monkeypatch.setattr(features, "PAID", frozenset({"tags"}))
    r = tag(three, app, ["one"], "work")
    assert r.status_code == 303 and all_tags(app) == []
    assert PAID in said(three)


def test_a_locked_toolbar_shows_a_disabled_button_and_no_tag_box(three, app, monkeypatch):
    monkeypatch.setattr(features, "PAID", frozenset({"tags"}))
    html = said(three)
    assert re.search(r'<button[^>]*disabled[^>]*>.*?Tag selected', html, re.S)
    assert "data-bulk-tags" not in html and 'class="bulk-tags"' not in html


# ---------- the toolbar itself ----------

def test_the_toolbar_has_the_panel_with_both_buttons(three, app):
    tag(three, app, ["one"], "work")
    html = said(three)
    start = html.index('class="bulk-tags"')
    panel = html[start:html.index("</details>", start)]
    assert "Tag selected" in panel and 'name="bulk_tags"' in panel and "data-bulk-tags" in panel
    assert re.search(
        r'id="bulk-tag-add"[^>]*formaction="/dashboard/links/tags"[^>]*value="add"', panel)
    assert re.search(r'formaction="/dashboard/links/tags"[^>]*value="remove"', panel)
    assert 'data-tag-pick="work"' in panel and 'data-target="bulk-tags-input"' in panel


def test_the_toolbar_form_has_no_text_box_before_the_delete_button_without_a_guard(three):
    """Enter in the tag box would press the toolbar's first button, 'Delete selected'. The page
    script must catch Enter there and press 'Add tags' instead."""
    js = Path("app/static/tags.js").read_text(encoding="utf-8")
    assert "data-bulk-tags" in js and "e.key !== 'Enter'" in js and "preventDefault" in js
    assert "bulk-tag-add" in js
    html = said(three)
    assert html.index('class="bulk-tags"') > html.index("Delete selected")  # why the guard matters
    assert "data-bulk-tags" in html


def test_the_messages_are_translated(three, app):
    three.cookies.set("lang", "hi")
    tag(three, app, ["one", "two"], "work")
    assert "2 लिंक पर टैग जोड़ दिए गए" in said(three).replace("२", "2")
    tag(three, app, ["one"], "work", action="remove")
    assert "लिंक से टैग हटा दिए गए" in said(three)
