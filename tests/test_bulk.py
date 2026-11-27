"""Bulk: change the same settings on many links at once (and add many from a file)."""
import re
from datetime import timedelta

import pytest

from app import alerts, features
from app.config import settings
from app.models import Link, LinkToggle, User, utcnow
from app.routers.bulk import MAX_BULK
from tests.conftest import register

PAID = "This feature is part of a paid plan."
URL = "https://example.com/"


@pytest.fixture()
def mail(alice, monkeypatch):
    """Email on AFTER alice exists, so alerts can be switched on; nothing really sent."""
    monkeypatch.setattr(settings, "email_backend", "console")
    monkeypatch.setattr(alerts, "send_email", lambda *a: True)


@pytest.fixture()
def four(alice, app):
    for slug in ("one", "two", "three", "four"):
        make(alice, slug)
    return alice


def make(client, slug, **extra):
    return client.post("/dashboard/links", data={"original_url": URL + slug, "slug": slug, **extra})


def row(app, slug):
    with app.state.session_factory() as db:
        link = db.query(Link).filter_by(slug=slug).one()
        list(link.tags)
        db.expunge(link)
        return link


def link_id(app, slug):
    return row(app, slug).id


def iso(delta):
    return (utcnow() + delta).isoformat()


def apply(client, app, slugs, **fields):
    return client.post("/dashboard/bulk", data={"ids": [link_id(app, s) for s in slugs], **fields})


def said(client):
    return client.get("/dashboard/bulk").text


def toggles(app):
    with app.state.session_factory() as db:
        return db.query(LinkToggle).count()


# ================= the page =================

def test_the_page_needs_an_account(make_client):
    r = make_client().get("/dashboard/bulk")
    assert r.status_code in (303, 401)


def test_the_page_lists_my_active_links_and_nobody_elses(four, app, make_client):
    bob = make_client()
    register(bob, "bobby")
    make(bob, "bobs")
    archive = {"ids": [link_id(app, "four")], "action": "archive"}
    four.post("/dashboard/links/archive", data=archive)
    four.get("/dashboard")                       # the "Archived 1 link(s)" message is used up here
    page = said(four)
    for slug in ("one", "two", "three"):
        assert f"/alice/{slug}<" in page
    assert "/alice/four<" not in page and "bobs" not in page
    assert page.count('name="ids"') == 3


def test_the_tag_bar_narrows_the_list(four, app):
    make(four, "work1", tags="work")
    make(four, "work2", tags="work")
    four.get("/dashboard")                       # earlier "Created ..." messages are used up here
    page = four.get("/dashboard/bulk?tag=work").text
    assert "/alice/work1<" in page and "/alice/work2<" in page and "/alice/one<" not in page
    assert 'href="/dashboard/bulk?tag=work#change"' in page


def test_an_empty_account_sees_the_empty_note(alice):
    page = said(alice)
    assert "No links yet" in page and 'name="ids"' not in page


def test_the_import_button_lives_here_and_not_on_the_dashboard(four):
    assert re.search(r'<a class="btn small ghost" href="/dashboard/links/import">'
                     r'Import many links from a CSV file</a>', said(four))
    assert "/dashboard/links/import" not in four.get("/dashboard").text


def test_a_locked_import_shows_why_and_no_button(four, monkeypatch):
    monkeypatch.setattr(features, "PAID", frozenset({"csv_import"}))
    page = said(four)
    assert 'href="/dashboard/links/import"' not in page and PAID in page


def test_every_setting_has_a_change_this_box_that_starts_unticked(four):
    page = said(four)
    for name in ("password", "start", "end", "limit", "status", "preview", "alerts", "qr"):
        box = re.search(rf'<input type="checkbox" name="change_{name}" value="1"[^>]*>', page)
        assert box and "checked" not in box.group(0), name


def test_the_page_carries_what_the_script_needs(four):
    page = said(four)
    form = re.search(r'<form[^>]*id="bulk-form"[^>]*>', page, re.S).group(0)
    assert f'data-max="{MAX_BULK}"' in form
    assert "This will change {n} link(s). Continue?" in form
    assert "{n} link selected." in form and "{n} links selected." in form
    assert '/static/bulk.js?v=' in page and 'id="bulk-all"' in page and 'id="bulk-go"' in page


# ================= the top bar =================

def test_bulk_sits_between_dashboard_and_guide(four, make_client):
    bar = four.get("/dashboard").text
    order = [bar.index(x) for x in ('href="/dashboard">Dashboard', 'href="/dashboard/bulk">Bulk',
                                    'href="/guide">Guide')]
    assert order == sorted(order)
    assert "/dashboard/bulk" not in make_client().get("/").text          # not for visitors


def test_on_the_narrowest_phones_it_moves_into_the_avatar_menu(four):
    from pathlib import Path
    css = Path("app/static/style.css").read_text(encoding="utf-8")
    page = four.get("/dashboard").text
    assert re.search(r'<a class="menu-item menu-bulk" href="/dashboard/bulk">Bulk</a>', page)
    assert re.search(r"\.menu-bulk \{ display: none; \}", css)
    small = css[css.index("@media (max-width: 370px)"):]
    small = small[:small.index("}\n}") + 3]
    assert ".nav-bulk { display: none; }" in small and ".menu-bulk { display: block; }" in small


# ================= changing settings =================

def test_a_password_goes_on_the_ticked_links_only(four, app, make_client):
    r = apply(four, app, ["one", "two"], change_password="1", password_action="set",
              new_password="open-sesame")
    assert r.status_code == 303 and r.headers["location"] == "/dashboard/bulk"
    assert row(app, "one").password_hash and row(app, "two").password_hash
    assert row(app, "three").password_hash is None
    assert "Changed 2 link(s)." in said(four)
    visitor = make_client()
    assert visitor.get("/alice/one").status_code == 200                    # asks for the password
    assert visitor.post("/alice/two", data={"password": "open-sesame"}).status_code == 302
    assert visitor.get("/alice/three").status_code == 302                  # untouched


def test_the_password_can_be_taken_off_many_links(four, app):
    for slug in ("one", "two"):
        edit = {"original_url": URL + slug, "password_action": "set", "new_password": "secret-1"}
        four.post(f"/dashboard/links/{link_id(app, slug)}/edit", data=edit)
    apply(four, app, ["one", "two"], change_password="1", password_action="remove")
    assert row(app, "one").password_hash is None and row(app, "two").password_hash is None


def test_a_bad_password_changes_nothing(four, app):
    apply(four, app, ["one", "two"], change_password="1", password_action="set", new_password="ab")
    assert "Link password must be" in said(four) or "password" in said(four).lower()
    assert row(app, "one").password_hash is None


def test_start_and_end_times(four, app):
    start, end = iso(timedelta(days=1)), iso(timedelta(days=9))
    apply(four, app, ["one", "two"], change_start="1", starts_at_utc=start,
          change_end="1", expires_at_utc=end)
    for slug in ("one", "two"):
        link = row(app, slug)
        assert link.starts_at is not None and link.expires_at is not None
    assert row(app, "three").starts_at is None and row(app, "three").expires_at is None


def test_an_empty_box_clears_a_time_when_its_box_is_ticked(four, app):
    apply(four, app, ["one"], change_end="1", expires_at_utc=iso(timedelta(days=9)))
    assert row(app, "one").expires_at is not None
    apply(four, app, ["one"], change_end="1", expires_at_utc="")
    assert row(app, "one").expires_at is None


def test_a_start_after_the_end_is_refused_for_everyone(four, app):
    apply(four, app, ["one", "two"], change_start="1", starts_at_utc=iso(timedelta(days=9)),
          change_end="1", expires_at_utc=iso(timedelta(days=1)))
    assert "The end time must be after the start time." in said(four)
    assert row(app, "one").starts_at is None and row(app, "two").expires_at is None


def test_a_link_whose_own_time_clashes_is_skipped_and_the_rest_are_changed(four, app):
    apply(four, app, ["one"], change_end="1", expires_at_utc=iso(timedelta(days=2)))
    apply(four, app, ["two"], change_start="1", starts_at_utc=iso(timedelta(days=1)))
    # a start in 5 days is fine for "two" but would come after the end of "one"
    apply(four, app, ["one", "two"], change_start="1", starts_at_utc=iso(timedelta(days=5)))
    page = said(four)
    assert "Changed 1 link(s)." in page
    assert "1 link(s) were skipped because their start time would not be before" in page
    assert row(app, "one").starts_at is None                      # left exactly as it was
    assert row(app, "two").starts_at is not None


def test_a_click_limit_on_and_off(four, app, make_client):
    apply(four, app, ["one", "two"], change_limit="1", click_limit="2")
    assert row(app, "one").click_limit == 2 == row(app, "two").click_limit
    assert row(app, "three").click_limit is None
    visitor = make_client()
    assert [visitor.get("/alice/one").status_code for _ in range(3)] == [302, 302, 410]
    apply(four, app, ["one"], change_limit="1", click_limit="")
    link = row(app, "one")
    assert link.click_limit is None and link.limit_reached_at is None
    assert visitor.get("/alice/one").status_code == 302


def test_a_limit_below_the_clicks_so_far_marks_it_reached(four, app, make_client):
    visitor = make_client()
    visitor.get("/alice/one")
    visitor.get("/alice/one")
    apply(four, app, ["one"], change_limit="1", click_limit="1")
    assert row(app, "one").limit_reached_at is not None
    assert visitor.get("/alice/one").status_code == 410


def test_a_bad_limit_changes_nothing(four, app):
    apply(four, app, ["one"], change_limit="1", click_limit="abc", change_status="1", status="off")
    assert row(app, "one").click_limit is None
    assert row(app, "one").is_active                          # not even the status


def test_switching_many_links_off_and_on(four, app, make_client):
    visitor = make_client()
    apply(four, app, ["one", "two"], change_status="1", status="off")
    assert not row(app, "one").is_active and not row(app, "two").is_active
    assert row(app, "three").is_active
    assert visitor.get("/alice/one").status_code == 403
    assert toggles(app) == 2
    apply(four, app, ["one", "two", "three"], change_status="1", status="on")
    assert visitor.get("/alice/one").status_code == 302
    assert toggles(app) == 4                       # "three" was already on: no history for it


def test_visitors_see_the_change_at_once_even_when_the_link_is_cached(four, app, make_client,
                                                                      redis_fake):
    redis_fake.flushall()
    visitor = make_client()
    assert visitor.get("/alice/one").status_code == 302                      # now in the cache
    apply(four, app, ["one"], change_status="1", status="off")
    assert visitor.get("/alice/one").status_code == 403
    apply(four, app, ["one"], change_status="1", status="on")
    apply(four, app, ["one"], change_password="1", password_action="set", new_password="secret-1")
    assert visitor.get("/alice/one").status_code == 200                      # now asks for it


def test_the_preview_page_on_and_off(four, app, make_client):
    apply(four, app, ["one", "two"], change_preview="1", preview="1", preview_message="Hello!")
    link = row(app, "one")
    assert link.preview is True and link.preview_message == "Hello!"
    assert row(app, "three").preview is False
    page = make_client().get("/alice/one")
    assert page.status_code == 200 and "Hello!" in page.text
    apply(four, app, ["one"], change_preview="1", preview="0", preview_message="ignored")
    link = row(app, "one")
    assert link.preview is False and link.preview_message is None


def test_email_alerts_for_links_that_can_use_them(four, app, mail):
    apply(four, app, ["one", "two"], change_limit="1", click_limit="5")
    apply(four, app, ["one", "two", "three"], change_alerts="1", alert_limit="1", alert_clicks="3")
    assert row(app, "one").alert_limit and row(app, "one").alert_clicks == 3
    assert row(app, "three").alert_limit is False                            # no limit: skipped
    page = said(four)
    assert "Changed 2 link(s)." in page
    assert "1 link(s) were skipped because the alerts you chose do not fit them" in page


def test_alerts_that_fit_no_link_say_so_and_change_nothing(four, app, mail):
    apply(four, app, ["one", "two"], change_alerts="1", alert_expiry="1")
    page = said(four)
    assert "No links were changed." in page
    assert "2 link(s) were skipped because the alerts you chose do not fit them" in page
    assert row(app, "one").alert_expiry is False


def test_a_new_limit_arms_the_limit_alert_again(four, app, mail):
    apply(four, app, ["one"], change_limit="1", click_limit="5", change_alerts="1", alert_limit="1")
    with app.state.session_factory() as db:
        db.query(Link).filter_by(slug="one").one().alert_limit_sent_at = utcnow()
        db.commit()
    apply(four, app, ["one"], change_limit="1", click_limit="9")
    assert row(app, "one").alert_limit_sent_at is None


def test_qr_colours_and_back_to_plain(four, app):
    apply(four, app, ["one", "two"], change_qr="1", qr_action="set", qr_fg="#112233",
          qr_bg="#f4f4f8")
    link = row(app, "one")
    assert (link.qr_fg, link.qr_bg) == ("#112233", "#f4f4f8")
    assert row(app, "three").qr_fg is None
    apply(four, app, ["one"], change_qr="1", qr_action="reset")
    link = row(app, "one")
    assert (link.qr_fg, link.qr_bg) == (None, None) and row(app, "two").qr_fg == "#112233"


def test_unreadable_qr_colours_are_refused_for_everyone(four, app):
    apply(four, app, ["one", "two"], change_qr="1", qr_action="set", qr_fg="#f4f4f8",
          qr_bg="#f4f4f6")
    assert row(app, "one").qr_fg is None and row(app, "two").qr_fg is None
    assert "Changed" not in said(four)


def test_a_reset_keeps_nothing_of_the_logo(four, app):
    with app.state.session_factory() as db:
        db.query(Link).filter_by(slug="one").one().qr_logo = b"\x89PNG-not-really"
        db.commit()
    apply(four, app, ["one"], change_qr="1", qr_action="reset")
    with app.state.session_factory() as db:
        assert db.query(Link).filter_by(slug="one").one().qr_logo is None


# ================= only what is ticked changes =================

def test_settings_that_are_not_ticked_are_ignored_even_if_values_arrive(four, app):
    apply(four, app, ["one"], change_status="1", status="off", click_limit="3",
          starts_at_utc=iso(timedelta(days=1)), new_password="secret-1", preview="1",
          alert_limit="1", qr_fg="#112233")
    link = row(app, "one")
    assert not link.is_active
    assert (link.click_limit, link.starts_at, link.password_hash, link.preview, link.qr_fg) \
        == (None, None, None, False, None)


def test_several_settings_can_change_in_one_go(four, app):
    apply(four, app, ["one", "two"], change_limit="1", click_limit="7", change_status="1",
          status="off", change_password="1", password_action="set", new_password="secret-1",
          change_end="1", expires_at_utc=iso(timedelta(days=3)))
    for slug in ("one", "two"):
        link = row(app, slug)
        assert (link.click_limit, link.is_active) == (7, False)
        assert link.password_hash and link.expires_at


def test_the_destination_and_the_short_name_never_change(four, app):
    before = row(app, "one")
    apply(four, app, ["one"], change_status="1", status="off", change_limit="1", click_limit="3")
    after = row(app, "one")
    assert (after.slug, after.original_url) == (before.slug, before.original_url)


# ================= mistakes and limits =================

def test_nothing_chosen(four, app):
    apply(four, app, [], change_status="1", status="off")
    assert "Select at least one link first." in said(four)
    r = apply(four, app, ["one"])
    assert r.status_code == 303 and "Choose at least one thing to change." in said(four)
    assert row(app, "one").is_active


def test_too_many_links_at_once(alice, app):
    ids = list(range(1, MAX_BULK + 2))
    r = alice.post("/dashboard/bulk", data={"ids": ids, "change_status": "1", "status": "off"})
    assert r.status_code == 303
    assert f"You can change up to {MAX_BULK} links at once." in said(alice)


def test_exactly_the_most_is_allowed(alice, app):
    with app.state.session_factory() as db:
        owner = db.query(User).one().id
        db.add_all(Link(user_id=owner, slug=f"s{n:04d}", original_url=URL + "x")
                   for n in range(MAX_BULK))
        db.commit()
        ids = [x for (x,) in db.query(Link.id)]
    alice.post("/dashboard/bulk", data={"ids": ids, "change_status": "1", "status": "off"})
    assert f"Changed {MAX_BULK} link(s)." in said(alice)


def test_the_same_link_ticked_twice_counts_once(four, app):
    one = link_id(app, "one")
    four.post("/dashboard/bulk", data={"ids": [one, one], "change_status": "1", "status": "off"})
    assert "Changed 1 link(s)." in said(four)


def test_somebody_elses_links_are_never_touched(four, app, make_client):
    bob = make_client()
    register(bob, "bobby")
    make(bob, "bobs")
    his, mine = link_id(app, "bobs"), link_id(app, "one")
    four.post("/dashboard/bulk", data={"ids": [his, mine], "change_status": "1", "status": "off"})
    assert row(app, "bobs").is_active and not row(app, "one").is_active
    assert "Changed 1 link(s)." in said(four)
    four.post("/dashboard/bulk", data={"ids": [his], "change_status": "1", "status": "off"})
    assert row(app, "bobs").is_active
    assert "Select at least one link first." in said(four)


def test_a_logged_out_visitor_cannot_use_it(four, app, make_client):
    r = make_client().post("/dashboard/bulk", data={"ids": [link_id(app, "one")],
                                                    "change_status": "1", "status": "off"})
    assert r.status_code in (303, 401) and row(app, "one").is_active


def test_pressing_it_over_and_over_is_slowed_down(four, app, redis_fake):
    redis_fake.flushall()
    one = link_id(app, "one")
    for _ in range(10):
        four.post("/dashboard/bulk", data={"ids": [one], "change_status": "1", "status": "on"})
    four.post("/dashboard/bulk", data={"ids": [one], "change_status": "1", "status": "off"})
    assert "Too many attempts. Try again later." in said(four) and row(app, "one").is_active


# ================= the paid-plan gate =================

def test_a_locked_account_sees_a_disabled_page_and_cannot_post_by_hand(four, app, monkeypatch):
    monkeypatch.setattr(features, "PAID", frozenset({"bulk_edit"}))
    page = said(four)
    assert PAID in page
    assert re.search(r'name="change_status"[^>]*disabled', page)
    assert re.search(r'id="bulk-go"[^>]*disabled', page) and 'data-locked="1"' in page
    assert re.search(r'name="ids"[^>]*disabled', page)
    r = apply(four, app, ["one"], change_status="1", status="off")
    assert r.status_code == 303 and row(app, "one").is_active
    assert PAID in said(four)


@pytest.mark.parametrize("feature,fields", [
    ("click_limit", {"change_limit": "1", "click_limit": "5"}),
    ("preview", {"change_preview": "1", "preview": "1"}),
    ("qr_style", {"change_qr": "1", "qr_action": "set", "qr_fg": "#112233", "qr_bg": "#f4f4f8"}),
])
def test_a_locked_feature_cannot_be_switched_on_through_bulk(four, app, monkeypatch,
                                                              feature, fields):
    monkeypatch.setattr(features, "PAID", frozenset({feature}))
    apply(four, app, ["one"], change_status="1", status="off", **fields)
    assert PAID in said(four)
    link = row(app, "one")
    assert link.is_active and link.click_limit is None and not link.preview and not link.qr_fg


def test_locked_alerts_cannot_be_switched_on_through_bulk(four, app, mail, monkeypatch):
    apply(four, app, ["one"], change_limit="1", click_limit="5")
    monkeypatch.setattr(features, "PAID", frozenset({"alerts"}))
    apply(four, app, ["one"], change_alerts="1", alert_limit="1")
    assert PAID in said(four) and row(app, "one").alert_limit is False


def test_going_back_to_basics_is_always_allowed(four, app, monkeypatch):
    apply(four, app, ["one"], change_limit="1", click_limit="5", change_qr="1", qr_action="set",
          qr_fg="#112233", qr_bg="#f4f4f8", change_preview="1", preview="1")
    monkeypatch.setattr(features, "PAID", frozenset({"click_limit", "preview", "qr_style"}))
    apply(four, app, ["one"], change_limit="1", click_limit="", change_preview="1", preview="0",
          change_qr="1", qr_action="reset")
    link = row(app, "one")
    assert link.click_limit is None and not link.preview and link.qr_fg is None


def test_a_locked_feature_card_is_shown_switched_off_with_a_note(four, monkeypatch):
    monkeypatch.setattr(features, "PAID", frozenset({"click_limit"}))
    page = said(four)
    card = page[page.index('name="change_limit"'):page.index('name="change_status"')]
    assert "disabled" in card.split("</legend>")[0] and PAID in card


def test_without_email_the_alerts_card_says_so(four):
    page = said(four)                                       # email is off in this test
    card = page[page.index('name="change_alerts"'):page.index('name="change_qr"')]
    assert "which is not set up on this server yet" in card
    assert re.search(r'name="change_alerts"[^>]*disabled', page)


# ================= languages =================

def test_the_page_and_messages_are_translated(four, app):
    four.cookies.set("lang", "hi")
    page = said(four)
    assert "कई लिंक एक साथ बदलें" in page and "यह बदलें" in page
    assert "Change many links at once" not in page
    apply(four, app, ["one"], change_status="1", status="off")
    assert "१ लिंक बदल दिए गए" in said(four)                # the number in Hindi digits
    four.cookies.set("lang", "gu")
    assert "ઘણી લિંક એકસાથે બદલો" in said(four)


def test_the_top_bar_link_is_translated(four):
    four.cookies.set("lang", "gu")
    assert 'href="/dashboard/bulk">બલ્ક</a>' in four.get("/dashboard").text


# ================= the script and style =================

def test_the_script_does_what_the_page_promises():
    from pathlib import Path
    js = Path("app/static/bulk.js").read_text(encoding="utf-8")
    for needle in ("bs-toggle", "bulk-all", "indeterminate", "window.confirm", "data-confirm",
                   "data-locked", "classList.add('ready')", "i18n-data"):
        assert needle in js, needle


def test_the_script_version_follows_the_file():
    from app.templating import templates
    assert templates.env.globals["js_version"]


def test_the_page_styles_use_only_the_colour_variables():
    from pathlib import Path
    css = Path("app/static/style.css").read_text(encoding="utf-8")
    block = css[css.index("/* ---- Bulk page ---- */"):]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgb\(|hsl\(", block)
    assert ".ready .bs:not(.on) .bs-body" in block          # dimmed only once the script runs
