"""Click limit: a link that stops working after N clicks (one-time links)."""

import re
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.activity import day_state, link_events
from app.models import Click, Link
from app.utils import MAX_CLICK_LIMIT, parse_click_limit, parse_device

LIMIT_MESSAGE = "This short link has reached its click limit."
BOT = "Mozilla/5.0 (compatible; Slackbot-LinkExpanding 1.0)"


def make(client, slug="lnk", **extra):
    return client.post("/dashboard/links", data={
        "original_url": "https://example.com/page", "slug": slug, **extra})


def info(app, slug="lnk"):
    with app.state.session_factory() as db:
        link = db.query(Link).filter_by(slug=slug).one()
        return SimpleNamespace(
            id=link.id, limit=link.click_limit, count=link.click_count,
            reached=link.limit_reached_at,
            rows=db.query(Click).filter_by(link_id=link.id).count(),
        )


def edit(client, link_id, **fields):
    data = {"original_url": "https://example.com/page", "password_action": "keep", **fields}
    if "click_limit" in fields:
        data["limit_box"] = "1"  # the edit page sends this along with its click-limit box
    return client.post(f"/dashboard/links/{link_id}/edit", data=data)


def visit(client, slug="lnk", **headers):
    return client.get(f"/alice/{slug}", headers=headers)


# ---- reading the box --------------------------------------------------------------------


@pytest.mark.parametrize("raw, expected", [
    ("", None), (None, None), ("   ", None), ("1", 1), (" 7 ", 7), ("1,000", 1000),
    ("१०", 10), ("૨૫", 25), (str(MAX_CLICK_LIMIT), MAX_CLICK_LIMIT),
])
def test_the_click_limit_box_is_read(raw, expected):
    assert parse_click_limit(raw) == expected


@pytest.mark.parametrize(
    "raw", ["0", "-1", "abc", "1.5", "1e3", str(MAX_CLICK_LIMIT + 1), "５", "1 2"]
)
def test_a_bad_click_limit_is_refused(raw):
    with pytest.raises(ValueError, match="whole number from 1 to 1,000,000"):
        parse_click_limit(raw)


def test_link_previews_are_recognised_as_robots():
    previews = (BOT, "WhatsApp/2.23.20.0 A", "facebookexternalhit/1.1", "TelegramBot (like Bot)")
    for ua in previews:
        assert parse_device(ua) == "bot", ua
    assert parse_device("Mozilla/5.0 (Windows NT 10.0) Chrome/126") == "desktop"


# ---- creating --------------------------------------------------------------------------


def test_a_link_can_be_created_with_a_limit(alice, app):
    make(alice, click_limit="5")
    assert info(app).limit == 5
    make(alice, "free")
    assert info(app, "free").limit is None


def test_a_bad_limit_creates_nothing_and_says_why(alice, app):
    make(alice, click_limit="zero")
    assert "The click limit must be a whole number" in alice.get("/dashboard").text
    with app.state.session_factory() as db:
        assert db.query(Link).count() == 0


# ---- following the link -----------------------------------------------------------------


def test_a_one_time_link_works_once(alice, app):
    make(alice, click_limit="1")
    first = visit(alice)
    assert first.status_code == 302 and first.headers["location"] == "https://example.com/page"
    second = visit(alice)
    assert second.status_code == 410 and LIMIT_MESSAGE in second.text
    after = info(app)
    assert after.count == 1 and after.rows == 1  # the refused visit was not counted


def test_the_limit_is_never_exceeded(alice, app):
    make(alice, click_limit="3")
    codes = [visit(alice).status_code for _ in range(6)]
    assert codes == [302, 302, 302, 410, 410, 410]
    assert info(app).count == 3


def test_the_moment_the_limit_was_used_is_remembered(alice, app):
    make(alice, click_limit="2")
    visit(alice)
    assert info(app).reached is None
    visit(alice)
    assert info(app).reached is not None


def test_a_link_without_a_limit_is_unchanged(alice, app):
    make(alice)
    assert [visit(alice).status_code for _ in range(4)] == [302] * 4
    assert info(app).count == 4 and info(app).reached is None


def test_link_preview_robots_do_not_use_up_a_one_time_link(alice, app):
    make(alice, click_limit="1")
    for ua in (BOT, "WhatsApp/2.23.20.0 A", "facebookexternalhit/1.1"):
        assert visit(alice, **{"user-agent": ua}).status_code == 302
    assert info(app).count == 0 and info(app).rows == 0  # not counted, not recorded
    assert visit(alice, **{"user-agent": "Mozilla/5.0 Chrome/126"}).status_code == 302  # a person
    assert visit(alice, **{"user-agent": "Mozilla/5.0 Chrome/126"}).status_code == 410
    assert visit(alice, **{"user-agent": BOT}).status_code == 410  # nothing left for robots either


def test_a_protected_link_uses_its_click_only_after_the_password(alice, app):
    make(alice, click_limit="1", link_password="secret1")
    assert "password" in visit(alice).text.lower()  # the form: no click used yet
    assert info(app).count == 0
    assert alice.post("/alice/lnk", data={"password": "wrong"}).status_code == 403
    assert info(app).count == 0
    done = alice.post("/alice/lnk", data={"password": "secret1"})
    assert done.status_code == 302 and info(app).count == 1
    gone = visit(alice)  # used up: the message, not the password form
    assert gone.status_code == 410 and LIMIT_MESSAGE in gone.text
    assert alice.post("/alice/lnk", data={"password": "secret1"}).status_code == 410


def test_the_refusal_is_translated(alice, client):
    make(alice, click_limit="1")
    visit(alice)
    client.cookies.set("lang", "hi")
    assert "क्लिक सीमा पूरी हो चुकी है" in client.get("/alice/lnk").text
    client.cookies.set("lang", "gu")
    assert "ક્લિક મર્યાદા પૂરી થઈ ગઈ છે" in client.get("/alice/lnk").text


def test_changing_the_limit_takes_effect_at_once_even_with_the_cache(alice, app, redis_fake):
    make(alice)
    assert visit(alice).status_code == 302  # now cached without a limit
    link_id = info(app).id
    edit(alice, link_id, click_limit="2")
    assert [visit(alice).status_code for _ in range(3)] == [302, 410, 410]  # one used already
    edit(alice, link_id, click_limit="")  # limit removed
    assert [visit(alice).status_code for _ in range(2)] == [302, 302]


# ---- editing --------------------------------------------------------------------------


def test_the_edit_page_shows_and_saves_the_limit(alice, app):
    make(alice, click_limit="4")
    link_id = info(app).id
    page = alice.get(f"/dashboard/links/{link_id}/edit").text
    assert 'name="click_limit"' in page and 'value="4"' in page
    assert "Click limit" in page and "0 clicks used so far." in page
    edit(alice, link_id, click_limit="9")
    assert info(app).limit == 9
    edit(alice, link_id, click_limit="")
    assert info(app).limit is None


def test_a_bad_limit_on_the_edit_page_changes_nothing(alice, app):
    make(alice, click_limit="4")
    link_id = info(app).id
    edit(alice, link_id, click_limit="-3")
    assert info(app).limit == 4
    assert "The click limit must be a whole number" in alice.get(
        f"/dashboard/links/{link_id}/edit").text


def test_leaving_the_box_out_keeps_the_limit(alice, app):
    make(alice, click_limit="4")
    edit(alice, info(app).id)  # a form without that box at all
    assert info(app).limit == 4


def test_raising_the_limit_brings_a_used_up_link_back(alice, app):
    make(alice, click_limit="1")
    visit(alice)
    assert visit(alice).status_code == 410 and info(app).reached is not None
    edit(alice, info(app).id, click_limit="3")
    assert info(app).reached is None
    assert [visit(alice).status_code for _ in range(3)] == [302, 302, 410]


def test_lowering_the_limit_below_the_clicks_so_far_closes_the_link(alice, app):
    make(alice)
    for _ in range(3):
        visit(alice)
    edit(alice, info(app).id, click_limit="2")
    assert visit(alice).status_code == 410
    assert info(app).reached is not None


# ---- what the owner sees --------------------------------------------------------------


def test_the_dashboard_shows_progress_and_the_status(alice, app):
    make(alice, click_limit="2")
    visit(alice)
    page = alice.get("/dashboard").text
    assert '1<small class="muted"> / 2</small>' in page and "Limit reached" not in page
    visit(alice)
    page = alice.get("/dashboard").text
    assert "Limit reached" in page and 'data-status="limit"' in page


def test_the_analytics_page_shows_usage_status_and_the_log_entry(alice, app):
    make(alice, click_limit="2")
    link_id = info(app).id
    visit(alice)
    page = alice.get(f"/dashboard/links/{link_id}").text
    assert "1 of 2 clicks used" in page and "Click limit reached" not in page
    visit(alice)
    page = alice.get(f"/dashboard/links/{link_id}").text
    assert "2 of 2 clicks used" in page and "Click limit reached" in page
    assert re.search(r'class="tag bad">Limit reached<', page)


def test_the_edit_page_says_the_link_is_at_its_limit(alice, app):
    make(alice, click_limit="1")
    visit(alice)
    page = alice.get(f"/dashboard/links/{info(app).id}/edit").text
    assert "Limit reached" in page and "1 click used so far." in page


@pytest.mark.parametrize("lang, word", [("hi", "सीमा पूरी"), ("gu", "મર્યાદા પૂરી")])
def test_the_limit_screens_render_in_every_language(alice, app, lang, word):
    make(alice, click_limit="1")
    visit(alice)
    alice.post("/language", data={"lang": lang, "next": "/"})
    link_id = info(app).id
    assert word in alice.get("/dashboard").text
    assert word in alice.get(f"/dashboard/links/{link_id}").text
    assert word in alice.get(f"/dashboard/links/{link_id}/edit").text


def test_the_create_form_has_the_advanced_box_and_the_new_label(alice):
    page = alice.get("/dashboard").text
    assert "More options: schedule, password and advanced" in page
    assert "schedule and password" not in page
    assert 'name="click_limit"' in page and "Advanced" in page


# ---- the activity log -----------------------------------------------------------------

NOW = datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc)
LIMIT_AT = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)


def fake(**fields):
    base = dict(created_at=NOW - timedelta(days=5), starts_at=None, expires_at=None)
    return SimpleNamespace(**{**base, **fields})


def test_days_after_the_limit_was_used_show_limit_reached():
    link = fake()
    states = [day_state(link, (NOW - timedelta(days=n)).date(), timezone.utc, NOW, (), LIMIT_AT)
              for n in (3, 2, 1, 0)]  # 11 Nov, 12 Nov, 13 Nov (the day it happened), 14 Nov
    assert states == ["active", "active", "partial", "limit"]


def test_without_a_limit_the_days_are_unchanged():
    assert day_state(fake(), NOW.date(), timezone.utc, NOW) == "active"


def test_the_earlier_of_expiry_and_limit_explains_a_closed_day():
    early_expiry = fake(expires_at=LIMIT_AT - timedelta(hours=6))
    assert day_state(early_expiry, NOW.date(), timezone.utc, NOW, (), LIMIT_AT) == "expired"
    late_expiry = fake(expires_at=LIMIT_AT + timedelta(hours=6))
    assert day_state(late_expiry, NOW.date(), timezone.utc, NOW, (), LIMIT_AT) == "limit"


def test_the_event_list_includes_the_limit():
    keys = [e["key"] for e in link_events(fake(), NOW, (), LIMIT_AT)]
    assert keys == ["created", "limit"]
    assert [e["key"] for e in link_events(fake(), NOW)] == ["created"]
