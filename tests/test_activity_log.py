"""The stats page's activity log (created / live / expired, clicks per day) and day view."""

import re
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.activity import day_state, link_events
from app.models import Click, Link, utcnow

IST = ZoneInfo("Asia/Kolkata")


def make(client, slug="lnk"):
    return client.post(
        "/dashboard/links", data={"original_url": "https://example.com/page", "slug": slug}
    )


def tweak(app, slug="lnk", **fields):
    with app.state.session_factory() as db:
        link = db.query(Link).filter_by(slug=slug).one()
        for name, value in fields.items():
            setattr(link, name, value)
        db.commit()
        return link.id


def add_click(app, when, slug="lnk", device="desktop"):
    with app.state.session_factory() as db:
        link = db.query(Link).filter_by(slug=slug).one()
        db.add(Click(link_id=link.id, clicked_at=when, device=device))
        db.commit()


def link_id(app, slug="lnk"):
    with app.state.session_factory() as db:
        return db.query(Link).filter_by(slug=slug).one().id


def log_row(page, day: date):
    """(status text, click count) of one day's row in the activity log."""
    m = re.search(
        rf'/day/{day.isoformat()}">[^<]*</a></td>\s*<td><span class="tag \w+">([^<]+)</span></td>'
        rf'\s*<td class="num">(\d+)</td>',
        page,
    )
    assert m, f"no log row for {day}"
    return m.group(1), int(m.group(2))


def at(day: datetime, hour: int, minute: int = 0) -> datetime:
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


# ---- the daily state of a link --------------------------------------------------------------

NOW = datetime(2026, 11, 9, 18, 0, tzinfo=timezone.utc)
TODAY = NOW.date()


def fake(created, starts=None, expires=None):
    return SimpleNamespace(created_at=created, starts_at=starts, expires_at=expires)


def test_unscheduled_link_is_active_every_day_including_the_day_it_was_made():
    link = fake(NOW - timedelta(days=3, hours=5))
    for back in range(0, 4):
        assert day_state(link, TODAY - timedelta(days=back), timezone.utc, NOW) == "active"


def test_a_link_made_a_second_ago_is_active():
    link = fake(NOW - timedelta(seconds=1))
    assert day_state(link, TODAY, timezone.utc, NOW) == "active"
    assert day_state(fake(NOW), TODAY, timezone.utc, NOW) == "active"


def test_scheduled_then_partly_active_then_active():
    link = fake(NOW - timedelta(days=5), starts=at(NOW, 12))
    assert day_state(link, TODAY - timedelta(days=1), timezone.utc, NOW) == "scheduled"
    assert day_state(link, TODAY, timezone.utc, NOW) == "partial"  # went live at 12:00 today


def test_active_then_partly_active_then_expired():
    link = fake(NOW - timedelta(days=5), expires=at(NOW - timedelta(days=1), 12))
    assert day_state(link, TODAY - timedelta(days=2), timezone.utc, NOW) == "active"
    assert day_state(link, TODAY - timedelta(days=1), timezone.utc, NOW) == "partial"
    assert day_state(link, TODAY, timezone.utc, NOW) == "expired"


def test_link_that_starts_later_today_is_scheduled_so_far_today():
    link = fake(NOW - timedelta(days=2), starts=at(NOW, 22))  # starts after "now"
    assert day_state(link, TODAY, timezone.utc, NOW) == "scheduled"


def test_day_state_uses_the_visitors_days():
    # live from 20:00 UTC on 8 Nov = 01:30 IST on 9 Nov: the whole IST day of 9 Nov is NOT live yet
    link = fake(NOW - timedelta(days=5), starts=datetime(2026, 11, 8, 20, 0, tzinfo=timezone.utc))
    assert day_state(link, date(2026, 11, 8), timezone.utc, NOW) == "partial"
    assert day_state(link, date(2026, 11, 8), IST, NOW) == "scheduled"
    assert day_state(link, date(2026, 11, 9), IST, NOW) == "partial"


def test_events_are_in_time_order_and_mark_the_future():
    link = fake(NOW - timedelta(days=2), starts=NOW + timedelta(days=1),
                expires=NOW + timedelta(days=3))
    events = link_events(link, NOW)
    assert [e["key"] for e in events] == ["created", "starts", "expires"]
    assert [e["future"] for e in events] == [False, True, True]


# ---- the stats page -------------------------------------------------------------------------


def test_stats_page_shows_created_time_log_and_timeline(alice, app):
    make(alice)
    tweak(app, created_at=utcnow() - timedelta(days=3))
    page = alice.get(f"/dashboard/links/{link_id(app)}").text
    assert "Activity log" in page and "created <time" in page and "Created" in page
    assert page.count("/day/") == 4  # three days ago ... today
    today = utcnow().date()
    assert log_row(page, today)[0] == "Active"
    assert "Click a day to see its clicks hour by hour." in page


def test_log_shows_scheduled_and_expired_days(alice, app):
    make(alice, "sched")
    tweak(app, "sched", created_at=utcnow() - timedelta(days=2),
          starts_at=utcnow() + timedelta(days=2))
    page = alice.get(f"/dashboard/links/{link_id(app, 'sched')}").text
    assert log_row(page, utcnow().date())[0] == "Scheduled"
    assert "Goes live" in page

    make(alice, "gone")
    tweak(app, "gone", created_at=utcnow() - timedelta(days=5),
          expires_at=utcnow() - timedelta(days=2))
    page = alice.get(f"/dashboard/links/{link_id(app, 'gone')}").text
    assert log_row(page, utcnow().date())[0] == "Expired"
    assert "Expired" in page


def test_log_is_cut_to_the_last_30_days(alice, app):
    make(alice)
    tweak(app, created_at=utcnow() - timedelta(days=100))
    page = alice.get(f"/dashboard/links/{link_id(app)}").text
    assert page.count("/day/") == 30
    assert "Showing the last 30 days." in page


def test_log_counts_clicks_in_the_visitors_own_days(alice, app):
    make(alice)
    tweak(app, created_at=utcnow() - timedelta(days=4))
    when = at(utcnow() - timedelta(days=1), 20)  # 20:00 UTC is 01:30 the next day in India
    add_click(app, when)
    url = f"/dashboard/links/{link_id(app)}"

    assert log_row(alice.get(url).text, when.date()) == ("Active", 1)  # no cookie: UTC days

    alice.cookies.set("tz", "Asia/Kolkata")
    page = alice.get(url).text
    assert "(Asia/Kolkata)" in page
    assert log_row(page, when.astimezone(IST).date())[1] == 1
    assert log_row(page, when.date())[1] == 0


@pytest.mark.parametrize("bad", ["../../etc/passwd", "Nope/Zone", "x" * 80, "A/B/C/D", ""])
def test_a_bad_time_zone_cookie_falls_back_to_utc(alice, app, bad):
    make(alice)
    alice.cookies.set("tz", bad)
    page = alice.get(f"/dashboard/links/{link_id(app)}")
    assert page.status_code == 200 and "(UTC)" in page.text


# ---- the hourly day view --------------------------------------------------------------------


def test_day_page_shows_clicks_hour_by_hour(alice, app):
    make(alice)
    tweak(app, created_at=utcnow() - timedelta(days=4))
    day = utcnow() - timedelta(days=1)
    add_click(app, at(day, 20, 5), device="mobile")
    add_click(app, at(day, 20, 40))
    add_click(app, at(day, 3, 0))
    lid = link_id(app)

    page = alice.get(f"/dashboard/links/{lid}/day/{day.date().isoformat()}")
    assert page.status_code == 200
    assert 'title="20:00 · 2"' in page.text and 'title="03:00 · 1"' in page.text
    assert page.text.count('class="bar"') == 24
    assert "Busiest hour: 20:00–21:00" in page.text
    assert "3 clicks" in page.text and "<span>mobile</span>" in page.text


def test_day_page_uses_the_visitors_time_zone(alice, app):
    make(alice)
    tweak(app, created_at=utcnow() - timedelta(days=4))
    when = at(utcnow() - timedelta(days=1), 20, 10)  # 01:40 next day in India
    add_click(app, when)
    alice.cookies.set("tz", "Asia/Kolkata")
    local_day = when.astimezone(IST).date().isoformat()
    page = alice.get(f"/dashboard/links/{link_id(app)}/day/{local_day}")
    assert page.status_code == 200
    assert 'title="01:00 · 1"' in page.text and "Busiest hour: 01:00–02:00" in page.text


def test_day_page_with_no_clicks_and_day_navigation(alice, app):
    make(alice)
    tweak(app, created_at=utcnow() - timedelta(days=3))
    lid = link_id(app)
    middle = (utcnow() - timedelta(days=1)).date()
    page = alice.get(f"/dashboard/links/{lid}/day/{middle.isoformat()}").text
    assert "No clicks on this day." in page
    assert f"/day/{(middle - timedelta(days=1)).isoformat()}" in page  # previous day
    assert f"/day/{utcnow().date().isoformat()}" in page  # next day
    today_page = alice.get(f"/dashboard/links/{lid}/day/{utcnow().date().isoformat()}").text
    assert "Next day" not in today_page


def test_day_page_rejects_bad_dates_and_other_peoples_links(alice, app, make_client):
    make(alice)
    tweak(app, created_at=utcnow() - timedelta(days=3))
    lid = link_id(app)
    for bad in ("not-a-date", "2026-13-40", (utcnow() + timedelta(days=2)).date().isoformat(),
                (utcnow() - timedelta(days=30)).date().isoformat()):
        assert alice.get(f"/dashboard/links/{lid}/day/{bad}").status_code == 404
    bob = make_client()
    bob.post("/register", data={"username": "bob", "email": "bob@example.com",
                                "password": "password123"})
    assert bob.get(f"/dashboard/links/{lid}/day/{utcnow().date().isoformat()}").status_code == 404


@pytest.mark.parametrize("lang", ["hi", "gu"])
def test_activity_pages_are_translated(alice, app, lang):
    make(alice)
    tweak(app, created_at=utcnow() - timedelta(days=2))
    lid = link_id(app)
    alice.post("/language", data={"lang": lang, "next": "/"})
    today = utcnow().date().isoformat()
    for url in (f"/dashboard/links/{lid}", f"/dashboard/links/{lid}/day/{today}"):
        page = alice.get(url).text
        assert "Activity log" not in page and "Clicks per hour" not in page
        assert "Click a day to see" not in page and "Busiest hour" not in page
