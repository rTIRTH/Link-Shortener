"""The optional preview page shown before a redirect."""

import re
from html import unescape

import pytest

from app import features
from app.models import Click, Link
from app.routers import redirect

DEST = "https://shop.example.com/summer-sale"


def make(client, slug="lnk", url=DEST, **extra):
    return client.post("/dashboard/links", data={"original_url": url, "slug": slug, **extra})


def info(app, slug="lnk"):
    with app.state.session_factory() as db:
        link = db.query(Link).filter_by(slug=slug).one()
        return {
            "id": link.id, "count": link.click_count, "preview": link.preview,
            "message": link.preview_message,
            "rows": db.query(Click).filter_by(link_id=link.id).count(),
        }


def edit(client, link_id, **fields):
    data = {"original_url": DEST, "password_action": "keep", **fields}
    if "preview" in fields or "preview_message" in fields:
        data["preview_box"] = "1"  # the edit page sends this along with its preview box
    return client.post(f"/dashboard/links/{link_id}/edit", data=data)


def token(page):
    return re.search(r'name="token" value="([^"]+)"', page).group(1)


def visit(client, slug="lnk", **headers):
    return client.get(f"/alice/{slug}", headers=headers)


def go(client, tok, slug="lnk"):
    return client.post(f"/alice/{slug}/continue", data={"token": tok})


# ---- turning it on ---------------------------------------------------------------------------


def test_a_link_has_no_preview_unless_asked(alice, app):
    make(alice)
    assert info(app)["preview"] is False
    r = visit(alice)
    assert r.status_code == 302 and r.headers["location"] == DEST  # straight through, as before


def test_a_preview_and_its_message_are_saved(alice, app):
    make(alice, preview="1", preview_message="  Thanks   for scanning!  ")
    assert info(app)["preview"] is True and info(app)["message"] == "Thanks for scanning!"


def test_a_message_without_the_tick_is_ignored(alice, app):
    make(alice, preview_message="hello")
    assert info(app)["preview"] is False and info(app)["message"] is None


def test_a_too_long_message_is_refused(alice, app):
    make(alice, preview="1", preview_message="x" * 201)
    assert "up to 200 characters" in alice.get("/dashboard").text
    with app.state.session_factory() as db:
        assert db.query(Link).count() == 0


def test_a_message_of_200_characters_is_fine(alice, app):
    make(alice, preview="1", preview_message="x" * 200)
    assert len(info(app)["message"]) == 200


# ---- what a visitor sees ---------------------------------------------------------------------


def test_the_preview_shows_where_the_link_goes_and_counts_nothing(alice, app):
    make(alice, preview="1", preview_message="This offer ends Friday")
    r = visit(alice)
    page = unescape(r.text)
    assert r.status_code == 200 and "location" not in r.headers
    assert "You're going to shop.example.com" in page and DEST in page
    assert "This offer ends Friday" in page and "Written by the link's owner" in page
    assert 'action="/alice/lnk/continue"' in page and "Continue" in page and "Go back" in page
    assert r.headers["x-robots-tag"] == "noindex" and r.headers["cache-control"] == "no-store"
    assert info(app)["count"] == 0 and info(app)["rows"] == 0  # looking is not a click


def test_without_a_message_there_is_no_message_box(alice):
    make(alice, preview="1")
    page = visit(alice).text
    assert "A message from the link" not in page and "<blockquote" not in page


def test_the_message_cannot_inject_html(alice):
    make(alice, preview="1", preview_message="<script>alert(1)</script><b>hi</b>")
    page = visit(alice).text
    assert "<script>alert" not in page and "&lt;script&gt;" in page and "<b>hi</b>" not in page


def test_continue_counts_the_click_and_redirects(alice, app):
    make(alice, preview="1")
    tok = token(visit(alice).text)
    r = go(alice, tok)
    assert r.status_code == 302 and r.headers["location"] == DEST
    assert info(app)["count"] == 1 and info(app)["rows"] == 1


def test_pressing_continue_twice_counts_twice_like_two_visits(alice, app):
    make(alice, preview="1")
    tok = token(visit(alice).text)
    assert go(alice, tok).status_code == 302 and go(alice, tok).status_code == 302
    assert info(app)["count"] == 2


@pytest.mark.parametrize("tok", ["", "garbage", "abc.def.ghi"])
def test_continue_without_a_real_token_starts_again_and_counts_nothing(alice, app, tok):
    make(alice, preview="1")
    r = go(alice, tok)
    assert r.status_code == 303 and r.headers["location"] == "/alice/lnk"
    assert info(app)["count"] == 0


def test_a_token_only_works_for_its_own_link(alice, app):
    make(alice, "one", preview="1")
    make(alice, "two", url="https://other.example.com/x", preview="1")
    tok = token(visit(alice, "one").text)
    r = go(alice, tok, "two")
    assert r.status_code == 303 and r.headers["location"] == "/alice/two"
    assert info(app, "two")["count"] == 0


def test_an_old_token_expires(alice, app, monkeypatch):
    make(alice, preview="1")
    tok = token(visit(alice).text)
    monkeypatch.setattr(redirect, "PREVIEW_TOKEN_SECONDS", -1)
    assert go(alice, tok).status_code == 303 and info(app)["count"] == 0


def test_a_link_switched_off_after_the_preview_stays_off(alice, app):
    make(alice, preview="1")
    tok = token(visit(alice).text)
    alice.post(f"/dashboard/links/{info(app)['id']}/toggle", data={"active": "0"})
    r = go(alice, tok)
    assert r.status_code == 403 and info(app)["count"] == 0


def test_robots_see_the_preview_and_use_nothing(alice, app):
    make(alice, preview="1", click_limit="1")
    r = visit(alice, **{"user-agent": "Slackbot-LinkExpanding 1.0"})
    assert r.status_code == 200 and "Continue" in r.text and info(app)["count"] == 0


def test_an_unknown_link_has_no_continue(alice):
    r = alice.post("/alice/nothing/continue", data={"token": "x"})
    assert r.status_code == 404


# ---- together with the other settings --------------------------------------------------------


def test_a_password_comes_first_then_the_preview(alice, app):
    make(alice, preview="1", preview_message="hi", link_password="secret1")
    first = visit(alice)
    assert "password" in first.text.lower() and "You're going to" not in unescape(first.text)
    wrong = alice.post("/alice/lnk", data={"password": "nope"})
    assert wrong.status_code == 403 and "You're going to" not in unescape(wrong.text)
    right = alice.post("/alice/lnk", data={"password": "secret1"})
    assert right.status_code == 200 and "You're going to" in unescape(right.text)
    assert info(app)["count"] == 0
    assert go(alice, token(right.text)).status_code == 302 and info(app)["count"] == 1


def test_the_password_cannot_be_skipped_by_going_straight_to_continue(alice, app):
    make(alice, preview="1", link_password="secret1")
    r = go(alice, "")
    assert r.status_code == 303 and r.headers["location"] == "/alice/lnk"
    assert info(app)["count"] == 0


def test_a_click_limit_is_used_only_when_continue_is_pressed(alice, app):
    make(alice, preview="1", click_limit="1")
    page = visit(alice)
    assert page.status_code == 200 and info(app)["count"] == 0
    tok = token(page.text)
    assert go(alice, tok).status_code == 302
    gone = visit(alice)  # used up: the message, not another preview
    assert gone.status_code == 410 and "click limit" in gone.text
    assert go(alice, tok).status_code == 410  # and the old button no longer works


def test_an_expired_link_shows_its_message_not_a_preview(alice, app):
    make(alice, preview="1")
    link_id = info(app)["id"]
    alice.post(f"/dashboard/links/{link_id}/toggle", data={"active": "0"})
    assert visit(alice).status_code == 403


# ---- the owner's side ------------------------------------------------------------------------


def test_the_edit_page_switches_it_on_and_off(alice, app, redis_fake):
    make(alice)
    assert visit(alice).status_code == 302  # now cached without a preview
    link_id = info(app)["id"]
    page = alice.get(f"/dashboard/links/{link_id}/edit").text
    assert 'name="preview"' in page and 'name="preview_message"' in page
    assert not re.search(r'name="preview"[^>]*checked', page)
    edit(alice, link_id, preview="1", preview_message="Hello")
    assert visit(alice).status_code == 200  # the change is live straight away
    assert info(app)["message"] == "Hello"
    on_page = alice.get(f"/dashboard/links/{link_id}/edit").text
    assert re.search(r'name="preview"[^>]*checked', on_page)
    edit(alice, link_id, preview_message="")  # the page posts the empty message, no tick
    assert visit(alice).status_code == 302 and info(app)["message"] is None


def test_saving_other_settings_does_not_lose_the_preview(alice, app):
    make(alice, preview="1", preview_message="Hello")
    edit(alice, info(app)["id"], click_limit="9", limit_box="1")
    assert info(app)["preview"] is True and info(app)["message"] == "Hello"


def test_the_list_marks_links_that_have_a_preview(alice):
    make(alice, "one", preview="1")
    make(alice, "two")
    page = alice.get("/dashboard").text
    assert page.count("Visitors see a preview page first") == 1


def test_the_create_form_has_the_tick_box_and_a_message_box(alice):
    page = alice.get("/dashboard").text
    assert 'name="preview"' in page and 'name="preview_message"' in page
    assert "Show a preview page before redirecting" in page and "pv-scope" in page


# ---- the paid-plan gate ----------------------------------------------------------------------


def test_a_locked_preview_cannot_be_switched_on(alice, app, monkeypatch):
    make(alice, "one", preview="1")
    monkeypatch.setattr(features, "PAID", frozenset({"preview"}))
    page = alice.get("/dashboard").text
    assert re.search(r'name="preview"[^>]*disabled', page) and "paid plan" in page
    make(alice, "two", preview="1")
    with app.state.session_factory() as db:
        assert db.query(Link).filter_by(slug="two").count() == 0
    assert visit(alice, "one").status_code == 200  # a preview set up earlier keeps working


def test_a_locked_edit_cannot_change_the_preview(alice, app, monkeypatch):
    make(alice, preview="1", preview_message="Hello")
    link_id = info(app)["id"]
    monkeypatch.setattr(features, "PAID", frozenset({"preview"}))
    edit(alice, link_id, original_url=DEST)  # what the locked page posts: no preview fields
    assert info(app)["preview"] is True and info(app)["message"] == "Hello"
    edit(alice, link_id, preview="", preview_message="")  # posting the box by hand
    assert info(app)["preview"] is True and info(app)["message"] == "Hello"


@pytest.mark.parametrize("lang, host_text", [
    ("hi", "आप shop.example.com पर जा रहे हैं"), ("gu", "તમે shop.example.com પર જઈ રહ્યા છો"),
])
def test_the_preview_page_is_translated(alice, client, lang, host_text):
    make(alice, preview="1", preview_message="Hello")
    client.cookies.set("lang", lang)
    page = unescape(visit(client).text)
    assert host_text in page
    for english in ("Before you continue", "Go back", "Only continue if you trust"):
        assert english not in page
