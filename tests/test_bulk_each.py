"""Bulk > One by one: every link has its own settings, saved together."""
import re
from datetime import timedelta
from html.parser import HTMLParser
from pathlib import Path

import pytest

from app import features
from app.config import settings
from app.models import Link, LinkEdit, LinkToggle, Tag, User, utcnow
from app.routers.bulk import MAX_BULK
from tests.conftest import register

PAID = "This feature is part of a paid plan."
URL = "https://example.com/"
PAGE = "/dashboard/bulk/each"


class FormFields(HTMLParser):
    """What a browser would post from the page: every named box, with the value it shows."""

    def __init__(self):
        super().__init__()
        self.fields, self._in_form = [], False
        self._select, self._seen_selected, self._first = None, False, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form" and a.get("id") == "each-form":
            self._in_form = True
        if not self._in_form:
            return
        if tag == "input" and a.get("name") and "disabled" not in a:
            if a.get("type") == "checkbox" and "checked" not in a:
                return
            self.fields.append((a["name"], a.get("value", "")))
        elif tag == "select" and a.get("name"):
            self._select, self._seen_selected, self._first = a["name"], False, None
        elif tag == "option" and self._select:
            if self._first is None:
                self._first = a.get("value", "")
            if "selected" in a:
                self.fields.append((self._select, a.get("value", "")))
                self._seen_selected = True

    def handle_endtag(self, tag):
        if tag == "select" and self._select:
            if not self._seen_selected:
                self.fields.append((self._select, self._first or ""))
            self._select = None
        if tag == "form":
            self._in_form = False


@pytest.fixture()
def mail(alice, monkeypatch):
    from app import alerts
    from app.config import settings
    monkeypatch.setattr(settings, "email_backend", "console")
    monkeypatch.setattr(alerts, "send_email", lambda *a: True)


def make(client, slug, **extra):
    return client.post("/dashboard/links", data={"original_url": URL + slug, "slug": slug, **extra})


def row(app, slug):
    with app.state.session_factory() as db:
        link = db.query(Link).filter_by(slug=slug).one()
        list(link.tags)
        db.expunge(link)
        return link


def lid(app, slug):
    return row(app, slug).id


def iso(delta):
    return (utcnow() + delta).isoformat()


def form(pairs):
    """(name, value) pairs -> what httpx sends as a form (a name used twice becomes a list)."""
    data = {}
    for name, value in pairs:
        data.setdefault(name, []).append(value)
    return data


def posted(client, url=PAGE):
    """The page's own fields, as (name, value) pairs - exactly what pressing Save would send."""
    parser = FormFields()
    parser.feed(client.get(url).text)
    return parser.fields


def save(client, app, changes=None, url=PAGE, **extra):
    """Press Save: post the page as it is, with `changes` = {slug: {field: value}} on top."""
    fields = posted(client, url)
    for slug, edits in (changes or {}).items():
        for field, value in edits.items():
            name = f"{field}_{lid(app, slug)}"
            fields = [(n, v) for (n, v) in fields if n != name] + [(name, value)]
    fields += list(extra.items())
    return client.post(PAGE, data=form(fields))


def said(client, url=PAGE):
    return client.get(url).text


@pytest.fixture()
def three(alice, app):
    for slug in ("one", "two", "three"):
        make(alice, slug)
    alice.get("/dashboard")                     # the "Created ..." messages are used up here
    return alice


# ================= the page =================

def test_the_page_needs_an_account(make_client):
    assert make_client().get(PAGE).status_code in (303, 401)


def test_every_link_gets_its_own_boxes(three, app):
    page = said(three)
    for slug in ("one", "two", "three"):
        i = lid(app, slug)
        for name in ("url", "start", "end", "limit", "active", "tags"):
            assert f'name="{name}_{i}"' in page, (slug, name)
        assert f'name="password_{i}"' in page
    assert page.count('name="ids"') == 3 and "Save all links" in page


def test_the_boxes_show_what_each_link_has_now(three, app):
    make(three, "rich", click_limit="5", tags="work, sale", link_password="secret-1",
         expires_at_utc="2027-06-30T10:30:00+00:00", starts_at_utc="2027-01-02T03:04:05+00:00")
    three.post(f"/dashboard/links/{lid(app, 'two')}/toggle", data={"active": "0"})
    page = said(three)
    i = lid(app, "rich")
    assert f'name="limit_{i}" value="5"' in page
    assert f'name="tags_{i}" value="sale, work"' in page \
        or f'name="tags_{i}" value="work, sale"' in page
    assert f'name="start_{i}" value="2027-01-02T03:04:05+00:00"' in page
    assert f'name="end_{i}" value="2027-06-30T10:30:00+00:00"' in page      # whole seconds only
    assert f'name="clear_password_{i}"' in page and "Leave empty to keep it" in page
    assert f'name="clear_password_{lid(app, "one")}"' not in page
    assert re.search(rf'name="active_{lid(app, "two")}">\s*<option value="1" >', page)
    assert re.search(rf'name="active_{lid(app, "two")}">.*?<option value="0" selected>', page, re.S)


def test_only_my_active_links_are_listed(three, app, make_client):
    bob = make_client()
    register(bob, "bobby")
    make(bob, "bobs")
    three.post("/dashboard/links/archive", data={"ids": [lid(app, "three")], "action": "archive"})
    three.get("/dashboard")
    page = said(three)
    assert "/alice/one<" in page and "/alice/three<" not in page and "bobs" not in page


def test_the_tag_bar_narrows_the_list(three, app):
    make(three, "work1", tags="work")
    three.get("/dashboard")
    page = three.get(PAGE + "?tag=work").text
    assert "/alice/work1<" in page and "/alice/one<" not in page


def test_chosen_links_only_with_a_way_back(three, app, make_client):
    bob = make_client()
    register(bob, "bobby")
    make(bob, "bobs")
    mine, his = lid(app, "one"), lid(app, "bobs")
    page = three.get(f"{PAGE}?ids={mine}&ids={his}").text
    assert page.count('name="ids"') == 1 and "/alice/one<" in page
    assert "Showing only the links you chose." in page and 'name="subset" value="1"' in page
    assert f'href="{PAGE}">Show all my links' in page


def test_both_bulk_pages_have_the_two_tabs(three):
    for url, current in (("/dashboard/bulk", "Same for all links"), (PAGE, "One by one")):
        page = three.get(url).text
        assert 'href="/dashboard/bulk"' in page and f'href="{PAGE}"' in page
        assert re.search(rf'class="on" aria-current="page">{current}</a>', page)


def test_an_empty_account(alice):
    assert "No links yet" in said(alice)


def test_a_very_long_list_stops_at_the_most_one_press_may_save(alice, app):
    with app.state.session_factory() as db:
        owner = db.query(User).one().id
        db.add_all(Link(user_id=owner, slug=f"s{n:04d}", original_url=URL + "x")
                   for n in range(MAX_BULK + 5))
        db.commit()
    page = said(alice)
    assert page.count('name="ids"') == MAX_BULK
    assert f"Only the first {MAX_BULK} links are shown." in page


# ================= saving =================

def test_saving_without_touching_anything_changes_nothing_at_all(three, app):
    make(three, "rich", click_limit="5", tags="work", link_password="secret-1",
         expires_at_utc="2027-06-30")                        # a bare date: "end of that day"
    three.post(f"/dashboard/links/{lid(app, 'two')}/toggle", data={"active": "0"})
    before = {s: row(app, s) for s in ("one", "two", "three", "rich")}
    r = save(three, app)
    assert r.status_code == 200 and "Nothing was changed." in r.text
    for slug, old in before.items():
        new = row(app, slug)
        for field in ("original_url", "starts_at", "expires_at", "password_hash", "click_limit",
                      "is_active", "limit_reached_at"):
            assert getattr(new, field) == getattr(old, field), (slug, field)
        assert sorted(t.name for t in new.tags) == sorted(t.name for t in old.tags)
    with app.state.session_factory() as db:
        assert db.query(LinkEdit).count() == 0 and db.query(LinkToggle).count() == 1


def test_each_link_can_get_a_different_change_in_one_save(three, app):
    r = save(three, app, {
        "one": {"url": "https://example.org/new-one", "limit": "5", "tags": "alpha"},
        "two": {"active": "0", "tags": "beta, gamma"},
    })
    assert r.status_code == 200 and "Saved 2 link(s)." in r.text
    one, two, three_ = row(app, "one"), row(app, "two"), row(app, "three")
    assert (one.original_url, one.click_limit, [t.name for t in one.tags]) \
        == ("https://example.org/new-one", 5, ["alpha"])
    assert (two.is_active, sorted(t.name for t in two.tags), two.click_limit) \
        == (False, ["beta", "gamma"], None)
    assert (three_.original_url, three_.is_active, three_.click_limit) \
        == (URL + "three", True, None)


def test_a_new_destination_is_remembered_in_the_history(three, app):
    save(three, app, {"one": {"url": "https://example.org/moved"}})
    with app.state.session_factory() as db:
        edit = db.query(LinkEdit).one()
        assert (edit.old_url, edit.new_url) == (URL + "one", "https://example.org/moved")


def test_visitors_see_the_changes_at_once_even_when_a_link_is_cached(three, app, make_client,
                                                                    redis_fake):
    redis_fake.flushall()
    visitor = make_client()
    assert visitor.get("/alice/one").headers["location"] == URL + "one"      # now cached
    save(three, app, {"one": {"url": "https://example.org/moved"}})
    assert visitor.get("/alice/one").headers["location"] == "https://example.org/moved"
    save(three, app, {"one": {"active": "0"}})
    assert visitor.get("/alice/one").status_code == 403


def test_a_bad_destination_is_refused_on_that_link_only(three, app):
    r = save(three, app, {"one": {"url": "not a web address"}, "two": {"limit": "9"}})
    assert r.status_code == 400
    page = r.text
    assert "Saved 1 link(s)." in page and "1 link(s) were not saved." in page
    assert row(app, "one").original_url == URL + "one" and row(app, "two").click_limit == 9
    assert 'class="each bad"' in page
    assert re.search(r'class="each-error" role="alert">[^<]+</p>', page)
    assert 'value="not a web address"' in page                     # what was typed is kept


def test_a_blocked_destination_and_the_sites_own_address_are_refused(three, app, monkeypatch):
    monkeypatch.setattr(settings, "blocked_domains", ("bad.test",))
    r = save(three, app, {"one": {"url": "https://bad.test/x"},
                          "two": {"url": "http://testserver/dashboard"}})
    assert r.status_code == 400 and "2 link(s) were not saved." in r.text
    assert row(app, "one").original_url == URL + "one"
    assert row(app, "two").original_url == URL + "two"


def test_passwords_can_be_different_on_every_link_and_taken_off(three, app, make_client):
    save(three, app, {"one": {"password": "first-pass"}, "two": {"password": "second-pass"}})
    visitor = make_client()
    assert visitor.post("/alice/one", data={"password": "first-pass"}).status_code == 302
    assert visitor.post("/alice/one", data={"password": "second-pass"}).status_code != 302
    assert visitor.post("/alice/two", data={"password": "second-pass"}).status_code == 302
    assert row(app, "three").password_hash is None
    save(three, app, {"one": {"clear_password": "1"}})
    assert row(app, "one").password_hash is None and row(app, "two").password_hash


def test_a_password_that_is_left_empty_keeps_the_old_one(three, app):
    save(three, app, {"one": {"password": "first-pass"}})
    old = row(app, "one").password_hash
    save(three, app)
    assert row(app, "one").password_hash == old


def test_a_short_password_is_refused_and_never_shown_again(three, app):
    r = save(three, app, {"one": {"password": "ab"}})
    assert r.status_code == 400 and "A link password must be 4-72 characters." in r.text
    assert 'value="ab"' not in r.text and row(app, "one").password_hash is None


def test_times_are_per_link_and_can_be_cleared(three, app):
    save(three, app, {
        "one": {"end": "2027-03-01T10:00:00.000Z"},
        "two": {"start": "2027-02-01T08:00:00.000Z", "end": "2027-04-01T08:00:00.000Z"},
    })
    one, two = row(app, "one"), row(app, "two")
    assert one.starts_at is None and one.expires_at.replace(tzinfo=None).isoformat() \
        == "2027-03-01T10:00:00"
    assert two.starts_at is not None and two.expires_at is not None
    save(three, app, {"one": {"end": ""}})
    assert row(app, "one").expires_at is None and row(app, "two").expires_at is not None


def test_a_start_after_the_end_is_refused_for_that_link(three, app):
    r = save(three, app, {"one": {"start": "2027-05-01T00:00:00Z", "end": "2027-04-01T00:00:00Z"},
                          "two": {"limit": "3"}})
    assert r.status_code == 400 and "The end time must be after the start time." in r.text
    assert row(app, "one").starts_at is None and row(app, "two").click_limit == 3


def test_a_garbled_time_is_refused(three, app):
    r = save(three, app, {"one": {"end": "soon-ish"}})
    assert r.status_code == 400 and "That date or time is not valid." in r.text


def test_a_click_limit_starts_afresh_and_can_be_taken_off(three, app, make_client):
    visitor = make_client()
    visitor.get("/alice/one")
    visitor.get("/alice/one")
    save(three, app, {"one": {"limit": "2"}})
    assert row(app, "one").limit_reached_at is not None
    assert visitor.get("/alice/one").status_code == 410
    save(three, app, {"one": {"limit": ""}})
    link = row(app, "one")
    assert link.click_limit is None and link.limit_reached_at is None
    assert visitor.get("/alice/one").status_code == 302


def test_a_bad_limit_is_refused_on_that_link(three, app):
    r = save(three, app, {"one": {"limit": "lots"}})
    assert r.status_code == 400 and 'value="lots"' in r.text


def test_switching_links_on_and_off_leaves_history_only_for_real_changes(three, app, make_client):
    save(three, app, {"one": {"active": "0"}, "two": {"active": "1"}})     # "two" already on
    assert not row(app, "one").is_active and row(app, "two").is_active
    with app.state.session_factory() as db:
        assert db.query(LinkToggle).count() == 1
    assert make_client().get("/alice/one").status_code == 403


def test_tags_can_be_different_and_unused_ones_disappear(three, app):
    save(three, app, {"one": {"tags": "alpha, beta"}, "two": {"tags": "beta"}})
    assert sorted(t.name for t in row(app, "one").tags) == ["alpha", "beta"]
    save(three, app, {"one": {"tags": "beta"}})
    with app.state.session_factory() as db:
        assert sorted(t.name for t in db.query(Tag)) == ["beta"]


def test_too_many_tags_on_one_link_is_refused_for_that_link(three, app):
    r = save(three, app, {"one": {"tags": "a, b, c, d, e, f"}, "two": {"tags": "ok"}})
    assert r.status_code == 400 and "A link can have up to 5 tags." in r.text
    assert row(app, "one").tags == [] and [t.name for t in row(app, "two").tags] == ["ok"]


def test_the_account_wide_tag_limit_leaves_that_link_exactly_as_it_was(three, app):
    with app.state.session_factory() as db:
        owner = db.query(User).one().id
        db.add_all(Tag(user_id=owner, name=f"t{n}") for n in range(50))
        db.commit()
    r = save(three, app, {"one": {"tags": "brand-new", "limit": "4", "active": "0"}})
    assert r.status_code == 400 and "You can have up to 50 tags in total." in r.text
    link = row(app, "one")
    assert link.tags == [] and link.click_limit is None and link.is_active      # nothing applied


def test_a_new_limit_or_end_arms_its_email_alert_again(three, app, mail):
    make(three, "alerted", click_limit="5", alert_limit="1", alert_expiry="1",
         expires_at_utc=iso(timedelta(days=9)))
    with app.state.session_factory() as db:
        link = db.query(Link).filter_by(slug="alerted").one()
        link.alert_limit_sent_at = link.alert_expiry_sent_at = utcnow()
        db.commit()
    save(three, app, {"alerted": {"limit": "8"}})
    link = row(app, "alerted")
    assert link.alert_limit_sent_at is None and link.alert_expiry_sent_at is not None
    save(three, app, {"alerted": {"end": iso(timedelta(days=12))}})
    assert row(app, "alerted").alert_expiry_sent_at is None


def test_somebody_elses_links_are_never_touched(three, app, make_client):
    bob = make_client()
    register(bob, "bobby")
    make(bob, "bobs")
    his = lid(app, "bobs")
    three.post(PAGE, data=form([("ids", his), (f"url_{his}", "https://evil.example/"),
                                (f"active_{his}", "0"), ("ids", "abc"), ("ids", "-3")]))
    assert row(app, "bobs").original_url == URL + "bobs" and row(app, "bobs").is_active


def test_the_same_link_twice_in_the_form_is_saved_once(three, app):
    one = lid(app, "one")
    r = three.post(PAGE, data=form([("ids", one), ("ids", one), (f"limit_{one}", "7")]))
    assert "Saved 1 link(s)." in r.text and row(app, "one").click_limit == 7


def test_pressing_save_over_and_over_is_slowed_down(three, app, redis_fake):
    redis_fake.flushall()
    for _ in range(10):
        save(three, app)
    save(three, app, {"one": {"limit": "3"}})
    assert row(app, "one").click_limit is None


def test_a_logged_out_visitor_cannot_save(three, app, make_client):
    one = lid(app, "one")
    r = make_client().post(PAGE, data=form([("ids", one), (f"limit_{one}", "7")]))
    assert r.status_code in (303, 401) and row(app, "one").click_limit is None


# ================= the paid-plan gate =================

def test_a_locked_account_sees_a_switched_off_page_and_cannot_post_by_hand(three, app,
                                                                            monkeypatch):
    monkeypatch.setattr(features, "PAID", frozenset({"bulk_edit"}))
    page = said(three)
    assert PAID in page and re.search(r'<fieldset class="each"\s+disabled>', page)
    assert re.search(r'<button class="btn" type="submit" disabled>', page)
    one = lid(app, "one")
    r = three.post(PAGE, data=form([("ids", one), (f"limit_{one}", "7"), (f"active_{one}", "0")]))
    assert r.status_code == 303 and row(app, "one").click_limit is None
    assert row(app, "one").is_active
    assert PAID in said(three)


def test_a_locked_click_limit_box_is_switched_off_and_cannot_be_posted(three, app, monkeypatch):
    monkeypatch.setattr(features, "PAID", frozenset({"click_limit"}))
    one = lid(app, "one")
    assert re.search(rf'name="limit_{one}"[^>]*disabled', said(three))
    r = save(three, app, {"one": {"limit": "9", "active": "0"}})
    assert r.status_code == 400 and PAID in r.text
    link = row(app, "one")
    assert link.click_limit is None and link.is_active                    # not even the status
    assert save(three, app, {"two": {"active": "0"}}).status_code == 200  # other rows are fine


def test_locked_tags_work_the_same_way(three, app, monkeypatch):
    monkeypatch.setattr(features, "PAID", frozenset({"tags"}))
    one = lid(app, "one")
    assert re.search(rf'name="tags_{one}"[^>]*disabled', said(three))
    r = save(three, app, {"one": {"tags": "sneaky"}})
    assert r.status_code == 400 and PAID in r.text and row(app, "one").tags == []


def test_locked_utm_cannot_be_added_through_the_destination_box(three, app, monkeypatch):
    monkeypatch.setattr(features, "PAID", frozenset({"utm"}))
    r = save(three, app, {"one": {"url": URL + "one?utm_source=news"}})
    assert r.status_code == 400 and PAID in r.text
    assert row(app, "one").original_url == URL + "one"
    # an ordinary change of destination is still fine
    assert "Saved 1 link(s)." in save(three, app, {"two": {"url": URL + "two-b"}}).text


# ================= after an import =================

CSV = (b"original_url,slug,tags\n"
       b"https://example.com/a1,imp-a,news\nhttps://example.com/a2,imp-b,\n")


def import_file(client):
    return client.post("/dashboard/links/import",
                       files={"file": ("links.csv", CSV, "text/csv")})


def test_the_import_result_offers_to_edit_the_new_links_one_by_one(three, app):
    r = import_file(three)
    ids = [lid(app, "imp-a"), lid(app, "imp-b")]
    link = re.search(
        r'<a [^>]*href="(/dashboard/bulk/each\?[^"]+)"[^>]*>Edit these links one by one', r.text)
    assert link, r.text
    href = link.group(1).replace("&amp;", "&")
    assert href == f"/dashboard/bulk/each?ids={ids[0]}&ids={ids[1]}"
    page = three.get(href).text
    assert page.count('name="ids"') == 2 and "/alice/imp-a<" in page and "/alice/one<" not in page


def test_a_failed_import_offers_nothing(three):
    r = three.post("/dashboard/links/import",
                   files={"file": ("links.csv", b"original_url\nnot a url\n", "text/csv")})
    assert "Edit these links one by one" not in r.text


def test_saving_from_that_page_keeps_showing_only_those_links(three, app):
    import_file(three)
    ids = [lid(app, "imp-a"), lid(app, "imp-b")]
    url = f"{PAGE}?ids={ids[0]}&ids={ids[1]}"
    r = save(three, app, {"imp-a": {"limit": "4"}}, url=url, subset="1")
    assert "Saved 1 link(s)." in r.text and r.text.count('name="ids"') == 2
    assert "Showing only the links you chose." in r.text and row(app, "imp-a").click_limit == 4


# ================= languages, script, style =================

def test_the_page_and_its_messages_are_translated(three, app):
    three.cookies.set("lang", "hi")
    assert "एक-एक करके" in said(three) and "सभी लिंक सहेजें" in said(three)
    r = save(three, app, {"one": {"url": "not a web address"}, "two": {"limit": "9"}})
    assert "सहेजे गए" in r.text and "सहेजे नहीं गए" in r.text
    assert "Saved 1 link(s)." not in r.text
    three.cookies.set("lang", "gu")
    assert "એક-એક કરીને" in said(three)


def test_the_script_keeps_the_exact_moment_in_a_hidden_box():
    js = Path("app/static/bulk.js").read_text(encoding="utf-8")
    for needle in ("each-form", "each-dt", "toISOString", "data-target", "fieldset.each",
                   "changed"):
        assert needle in js, needle


def test_the_cards_use_only_the_colour_variables():
    css = Path("app/static/style.css").read_text(encoding="utf-8")
    block = css[css.index("/* ---- Bulk: one by one"):]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgb\(|hsl\(", block)
    assert ".each.changed" in block and "position: sticky" in block
