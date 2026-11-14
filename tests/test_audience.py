"""Audience analytics: sources, devices, countries and cities, unique visitors, best time."""

import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app import insights
from app.charts import donut_svg, heat_level, heatmap_svg
from app.insights import (
    audience,
    classify_source,
    client_address,
    clean_city,
    clean_country,
    country_name,
    geo_from_headers,
    lookup_geo,
    parse_agent,
    rank_rows,
    visitor_id,
)
from app.models import Click, Link, utcnow

IST = ZoneInfo("Asia/Kolkata")
CHROME_WIN = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/126.0.0.0 Safari/537.36")
SAFARI_IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
                 "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")
CHROME_ANDROID = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/126.0.0.0 Mobile Safari/537.36")


def make(client, slug="lnk"):
    return client.post(
        "/dashboard/links", data={"original_url": "https://example.com/page", "slug": slug}
    )


def add(app, when=None, slug="lnk", **fields):
    with app.state.session_factory() as db:
        link = db.query(Link).filter_by(slug=slug).one()
        db.add(Click(link_id=link.id, clicked_at=when or utcnow(), **fields))
        db.commit()
        return link.id


def row(**fields):
    base = dict(clicked_at=utcnow(), device="desktop", referrer=None, source=None, browser=None,
                os=None, country=None, city=None, visitor=None)
    return SimpleNamespace(**{**base, **fields})


# ---- sources -------------------------------------------------------------------------------


@pytest.mark.parametrize("host, ua, tag, expected", [
    ("l.instagram.com", None, None, "instagram"),
    ("www.facebook.com", None, None, "facebook"),
    ("t.co", None, None, "x"),
    ("twitter.com", None, None, "x"),
    ("com.google.android.gm", None, None, "email"),  # the Gmail app on Android
    ("com.whatsapp", None, None, "whatsapp"),
    ("com.example.unknownapp", None, None, "website"),
    ("com.google.android.apps.maps", None, None, "website"),  # a Google app, not google.com
    ("www.google.com.au", None, None, "google"),
    ("mail.google.com", None, None, "email"),  # Gmail beats plain Google
    ("www.google.co.in", None, None, "google"),
    ("notgoogle.com", None, None, "website"),
    ("box.com", None, None, "website"),  # ends with "x.com" but is not x.com
    ("youtu.be", None, None, "youtube"),
    ("example.org", None, None, "website"),
    (None, None, None, "direct"),
    ("", "Mozilla/5.0 Instagram 300.0 Android", None, "instagram"),  # in-app browser, no referrer
    (None, "Mozilla/5.0 [FBAN/FBIOS;FBAV/450]", None, "facebook"),
    (None, CHROME_WIN, "whatsapp", "whatsapp"),  # ?ref=whatsapp names it
    (None, CHROME_WIN, "WA", "whatsapp"),
    ("example.org", None, "twitter", "x"),  # the owner's tag wins over the referrer
    (None, CHROME_WIN, "my-own-word", "direct"),  # unknown tags are ignored
    ("example.org:8080", None, None, "website"),
])
def test_where_the_click_came_from(host, ua, tag, expected):
    assert classify_source(host, ua, tag) == expected


def test_source_names_are_translated_only_when_they_are_words():
    assert insights.source_label("hi", "instagram") == "Instagram"  # a brand stays as it is
    assert insights.source_label("hi", "direct") == "सीधे"
    assert insights.source_label("gu", "website") != "Other websites"
    assert insights.source_label("en", "website") == "Other websites"


# ---- devices, browsers, systems ---------------------------------------------------------------


@pytest.mark.parametrize("ua, expected", [
    (CHROME_WIN, ("desktop", "chrome", "windows")),
    (SAFARI_IPHONE, ("mobile", "safari", "ios")),
    (CHROME_ANDROID, ("mobile", "chrome", "android")),
    (CHROME_WIN + " Edg/126.0", ("desktop", "edge", "windows")),
    ("Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
     ("desktop", "firefox", "linux")),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605 Version/17 Safari/605",
     ("desktop", "safari", "macos")),
    ("Mozilla/5.0 (Linux; Android 13) SamsungBrowser/24.0 Chrome/117 Mobile Safari/537",
     ("mobile", "samsung", "android")),
    ("Mozilla/5.0 (iPhone) AppleWebKit Mobile Instagram 300.0", ("mobile", "inapp", "ios")),
    ("Googlebot/2.1 (+http://www.google.com/bot.html)", ("bot", "other", "other")),
    ("", ("desktop", "unknown", "unknown")),
    (None, ("desktop", "unknown", "unknown")),
])
def test_browser_system_and_device_are_recognised(ua, expected):
    assert parse_agent(ua) == expected


# ---- where they are ---------------------------------------------------------------------------


def test_country_and_city_come_from_the_hosting_headers():
    assert geo_from_headers({"cf-ipcountry": "in", "cf-ipcity": "Vadodara"}) == ("IN", "Vadodara")
    assert geo_from_headers({"x-vercel-ip-country": "US", "x-vercel-ip-city": "New%20York"}) == (
        "US", "New York")
    assert geo_from_headers({"cf-ipcountry": "XX"}) == (None, None)  # Cloudflare's "unknown"
    assert geo_from_headers({"cf-ipcountry": "India"}) == (None, None)
    assert geo_from_headers({"cf-ipcity": "Paris"}) == (None, None)  # a city alone is not used
    assert geo_from_headers({}) == (None, None)


def test_clean_helpers():
    assert clean_country(" gb ") == "GB" and clean_country("T1") is None
    assert clean_country("") is None
    assert clean_city("  ") is None and clean_city("Unknown") is None
    assert clean_city("Surat") == "Surat"
    assert len(clean_city("x" * 300)) == 80


def test_the_visitors_address_is_found_behind_the_proxy():
    assert client_address({"true-client-ip": "8.8.8.8"}, "10.0.0.1") == "8.8.8.8"
    assert client_address({"x-forwarded-for": "1.2.3.4, 10.0.0.2"}, "10.0.0.1") == "1.2.3.4"
    assert client_address({}, "10.0.0.1") == "10.0.0.1"
    assert client_address({}, None) is None


def test_country_names_come_from_the_tz_database():
    assert country_name("IN") == "India"
    assert country_name("ZZ") == "ZZ"  # not a country: the code is shown as it is


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data


def test_geo_lookup_asks_once_and_remembers(monkeypatch, redis_fake):
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return FakeResponse({"status": "success", "countryCode": "IN", "city": "Vadodara"})

    monkeypatch.setattr(insights.httpx, "get", fake_get)
    assert lookup_geo("8.8.8.8") == ("IN", "Vadodara")
    assert lookup_geo("8.8.8.8") == ("IN", "Vadodara")
    assert len(calls) == 1 and "8.8.8.8" in calls[0]


def test_geo_lookup_never_breaks_a_click(monkeypatch, redis_fake):
    def boom(url, timeout):
        raise insights.httpx.ConnectError("offline")

    monkeypatch.setattr(insights.httpx, "get", boom)
    assert lookup_geo("8.8.8.8") == (None, None)

    failed = FakeResponse({"status": "fail"})
    monkeypatch.setattr(insights.httpx, "get", lambda url, timeout: failed)
    assert lookup_geo("1.1.1.1") == (None, None)


@pytest.mark.parametrize(
    "address", ["10.0.0.5", "127.0.0.1", "192.168.1.9", "testclient", "", None]
)
def test_private_addresses_are_never_looked_up(monkeypatch, address):
    monkeypatch.setattr(insights.httpx, "get", lambda *a, **k: pytest.fail("must not be called"))
    assert lookup_geo(address) == (None, None)


def test_geo_lookup_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(insights.settings, "geo_lookup", False)
    monkeypatch.setattr(insights.httpx, "get", lambda *a, **k: pytest.fail("must not be called"))
    assert lookup_geo("8.8.8.8") == (None, None)


# ---- unique visitors ----------------------------------------------------------------------


def test_the_same_device_gives_the_same_visitor_id_and_no_ip_is_kept():
    a = visitor_id("1.2.3.4", CHROME_WIN)
    assert a == visitor_id("1.2.3.4", CHROME_WIN) and len(a) == 16
    assert a != visitor_id("1.2.3.5", CHROME_WIN) and a != visitor_id("1.2.3.4", SAFARI_IPHONE)
    assert "1.2.3.4" not in a


def test_a_click_records_everything_about_the_visitor(alice, app):
    make(alice)
    hdr = {"user-agent": SAFARI_IPHONE, "referer": "https://l.instagram.com/?u=x",
           "cf-ipcountry": "IN", "cf-ipcity": "Vadodara"}
    alice.get("/alice/lnk", headers=hdr)
    alice.get("/alice/lnk", headers=hdr)  # the same person again
    alice.get("/alice/lnk", headers={"user-agent": CHROME_WIN})  # someone else, no referrer
    with app.state.session_factory() as db:
        first, again, other = db.query(Click).order_by(Click.id).all()
    assert (first.source, first.device, first.browser, first.os) == (
        "instagram", "mobile", "safari", "ios")
    assert (first.country, first.city) == ("IN", "Vadodara")
    assert first.referrer == "l.instagram.com"
    assert first.visitor == again.visitor != other.visitor
    assert (other.source, other.country, other.city) == ("direct", None, None)


def test_ref_in_the_address_names_the_source(alice, app):
    make(alice)
    alice.get("/alice/lnk?ref=whatsapp", headers={"user-agent": CHROME_ANDROID})
    alice.get("/alice/lnk?utm_source=newsletter", headers={"user-agent": CHROME_ANDROID})
    with app.state.session_factory() as db:
        assert [c.source for c in db.query(Click).order_by(Click.id)] == ["whatsapp", "email"]


def test_unique_and_returning_visitors_are_counted_separately():
    rows = [row(visitor="a"), row(visitor="a"), row(visitor="a"), row(visitor="b"),
            row(visitor="c"), row(visitor="c"), row(visitor=None)]
    data = audience(rows, IST, "en")
    assert data["total"] == 7 and data["unique"] == 3 and data["returning"] == 2
    assert data["untracked"] == 1  # an old click, from before visitors were recorded


# ---- the numbers --------------------------------------------------------------------------


def test_ranked_rows_have_shares_and_bar_widths():
    rows = rank_rows(Counter({"a": 6, "b": 3, "c": 1}), str.upper, limit=2)
    assert [r["label"] for r in rows] == ["A", "B"]
    assert [r["pct"] for r in rows] == [60, 30]
    assert [r["width"] for r in rows] == [100, 50]
    assert rank_rows(Counter(), str) == []


def test_old_clicks_still_show_a_source_from_their_referrer():
    rows = [row(referrer="www.facebook.com"), row(referrer=None), row(source="whatsapp")]
    data = audience(rows, IST, "en")
    found = {r["key"]: r["n"] for r in data["sources"]}
    assert found == {"facebook": 1, "direct": 1, "whatsapp": 1}


def test_places_only_count_clicks_that_have_a_location():
    rows = [row(country="IN", city="Surat"), row(country="IN", city="Surat"),
            row(country="IN"), row(country="US", city="Austin"), row()]
    data = audience(rows, IST, "en")
    assert [(r["code"], r["n"]) for r in data["countries"]] == [("IN", 3), ("US", 1)]
    assert [(r["label"], r["code"], r["n"]) for r in data["cities"]] == [
        ("Surat", "IN", 2), ("Austin", "US", 1)]
    assert data["no_location"] == 1
    assert data["countries"][0]["label"] == "India"


def test_best_time_uses_the_visitors_own_time_zone():
    # Friday 2026-11-13 18:30 UTC is Saturday 00:00 in India
    when = datetime(2026, 11, 13, 18, 30, tzinfo=timezone.utc)
    clicks = [row(clicked_at=when)] * 3 + [row(clicked_at=when + timedelta(days=1))]
    data = audience(clicks, IST, "en")
    assert data["best"] == {"day": 5, "hour": 0} and data["peak"] == 3  # Saturday, midnight
    assert data["grid"][5][0] == 3 and sum(map(sum, data["grid"])) == 4
    in_utc = audience([row(clicked_at=when)], timezone.utc, "en")
    assert in_utc["best"] == {"day": 4, "hour": 18}  # Friday, 18:00
    assert audience([], IST, "en")["best"] is None


def test_weekday_names_follow_the_language():
    assert insights.weekday_name("en", 0) == "Monday" and insights.weekday_name("en", 6) == "Sunday"
    assert insights.weekday_name("hi", 0) == "सोमवार"
    assert insights.weekday_name("en", 4, short=True) == "Fr"


# ---- the drawings -----------------------------------------------------------------------


def test_heat_levels():
    assert [heat_level(n, 8) for n in (0, 1, 2, 3, 4, 5, 8)] == [0, 1, 1, 2, 2, 3, 4]
    assert heat_level(5, 0) == 0


def test_heatmap_has_a_square_for_every_hour_of_every_weekday():
    grid = [[0] * 24 for _ in range(7)]
    grid[2][14] = 9
    grid[0][1] = 1
    tips = [[f"t{d}-{h}" for h in range(24)] for d in range(7)]
    svg = str(heatmap_svg(grid, list("MTWTFSS"), [f"{h:02d}" for h in range(24)], tips, aria="Hm"))
    assert svg.count('class="hm-cell') == 168
    assert 'hm-l4" x=' in svg and "<title>t2-14</title>" in svg and 'aria-label="Hm"' in svg
    assert svg.count("hm-l4") == 1 and svg.count("hm-l1") == 1
    assert svg.count('class="c-text"') == 7 + 8  # 7 weekdays + a label every 3 hours


def test_heatmap_hour_labels_use_native_digits():
    grid = [[0] * 24 for _ in range(7)]
    labels = [native_hour(h) for h in range(24)]
    svg = str(heatmap_svg(grid, list("1234567"), labels, [[""] * 24] * 7, aria="x"))
    assert "०९" in svg


def native_hour(h):
    from app.i18n import native_digits
    return native_digits("hi", f"{h:02d}")


def test_donut_slices_add_up_to_the_whole_ring():
    svg = str(donut_svg([{"n": 3, "tip": "a"}, {"n": 1, "tip": "b"}, {"n": 0, "tip": "c"}],
                        aria="Devices", center="4"))
    segs = re.findall(r'stroke:var\(--s(\d)\)" stroke-dasharray="([\d.]+) ([\d.]+)"', svg)
    assert [s[0] for s in segs] == ["1", "2"]  # an empty slice is not drawn
    assert [float(s[1]) for s in segs] == [75.0, 25.0]
    assert 'class="dn-text"' in svg and ">4</text>" in svg
    assert "<circle" in str(donut_svg([], aria="x", center="0"))  # an empty ring still draws


# ---- the page ---------------------------------------------------------------------------


def audience_box(page: str) -> str:
    start = page.index('<section class="audience"')
    return page[start:page.index("</section>", start)]


def test_the_page_says_so_when_there_are_no_clicks(alice, app):
    make(alice)
    with app.state.session_factory() as db:
        link_id = db.query(Link).one().id
    box = audience_box(alice.get(f"/dashboard/links/{link_id}").text)
    assert "No clicks in this period yet." in box
    assert "heatmap" not in box and 'class="rank"' not in box


def seed(app):
    now = utcnow()
    link_id = add(app, now, source="instagram", device="mobile", browser="safari", os="ios",
                  country="IN", city="Vadodara", visitor="v1")
    add(app, now, source="instagram", device="mobile", browser="safari", os="ios",
        country="IN", city="Vadodara", visitor="v1")
    add(app, now, source="whatsapp", device="mobile", browser="chrome", os="android",
        country="US", city="Austin", visitor="v2")
    add(app, now - timedelta(days=40), source="direct", device="desktop", browser="firefox",
        os="linux", visitor="v3")
    add(app, now, referrer="www.facebook.com", device="desktop")  # an old click: no details
    return link_id


def test_the_audience_section_shows_every_breakdown(alice, app):
    make(alice)
    link_id = seed(app)
    page = alice.get(f"/dashboard/links/{link_id}", headers={"accept-language": "en"}).text
    box = audience_box(page)
    for heading in ("Sources", "Devices", "Browsers", "Operating systems", "Countries", "Cities",
                    "Best time of day", "Where clicks come from", "Where visitors are"):
        assert heading in box, heading
    assert "<span>Instagram</span>" in box and "<span>WhatsApp</span>" in box
    assert "<span>Facebook</span>" in box  # the old click, worked out from its referrer
    assert "<span>India</span>" in box and "<span>Vadodara</span>" in box
    assert '<b class="rk-code">IN</b>' in box
    assert "<span>Safari</span>" in box and "<span>iOS</span>" in box
    assert 'class="chart-svg heatmap"' in box and 'class="chart-svg donut"' in box
    assert "clicks have no location yet" in box or "click has no location yet" in box
    assert "Clicks recorded before visitor tracking" in box  # one click has no visitor id
    assert "?ref=whatsapp" in box


def test_stat_tiles_show_clicks_unique_and_returning(alice, app):
    make(alice)
    link_id = seed(app)
    box = audience_box(alice.get(f"/dashboard/links/{link_id}").text)
    tiles = dict(re.findall(
        r'stat-label">([^<]+)</div>\s*<div class="stat-value">([^<]+)</div>', box))
    # last 30 days: 4 clicks (the 40-day-old one is outside), visitors v1 (twice) and v2
    assert tiles["Clicks"] == "4" and tiles["Unique visitors"] == "2"
    assert tiles["Returning visitors"] == "1"
    assert "50% of visitors clicked more than once." in box


def test_the_period_switch_changes_what_is_counted(alice, app):
    make(alice)
    link_id = seed(app)
    url = f"/dashboard/links/{link_id}"

    def clicks(period):
        box = audience_box(alice.get(url + period).text)
        return re.search(r'stat-label">Clicks</div>\s*<div class="stat-value">(\d+)<', box).group(1)

    assert clicks("") == clicks("?range=30") == "4"
    assert clicks("?range=7") == "4" and clicks("?range=90") == "5"
    assert clicks("?range=365") == "5"
    assert clicks("?range=12") == clicks("?range=abc") == "4"  # unknown choices use the default
    box = audience_box(alice.get(url + "?range=90").text)
    assert re.findall(r'<a href="\?range=(\d+)#audience"', box) == ["7", "30", "90", "365"]
    assert re.findall(r'<a href="\?range=(\d+)#audience" class="on"', box) == ["90"]
    assert "Last 7 days" in box and "Last 365 days" in box


def test_the_visitors_chart_sits_next_to_clicks_per_day(alice, app):
    make(alice)
    link_id = seed(app)
    page = alice.get(f"/dashboard/links/{link_id}").text
    card = page[page.index("Visitors per day"):]
    card = card[:card.index("</figure>")]
    assert "Unique visitors" in page and "Clicks" in card
    assert "Unique visitors: 2" in card  # today: v1 and v2
    assert "2 unique visitors in the last 14 days" in page


def test_audience_is_per_link_and_private(alice, make_client, app):
    make(alice)
    link_id = seed(app)
    bob = make_client()
    bob.post("/register", data={"username": "bob", "email": "bob@example.com",
                                "password": "password123"})
    assert bob.get(f"/dashboard/links/{link_id}").status_code == 404


@pytest.mark.parametrize("lang, last, digits", [
    ("hi", "पिछले ३० दिन", "२"), ("gu", "છેલ્લા ૩૦ દિવસ", "૨"),
])
def test_the_audience_section_is_translated_with_native_digits(alice, app, lang, last, digits):
    make(alice)
    link_id = seed(app)
    alice.post("/language", data={"lang": lang, "next": "/"})
    box = audience_box(alice.get(f"/dashboard/links/{link_id}").text)
    assert last in box and "Sources" not in box and "Unique visitors" not in box
    assert 'class="stat-value">४<' in box or 'class="stat-value">૪<' in box  # four clicks
    assert "Instagram" in box  # brand names stay as they are
    assert "<span>India</span>" in box  # place names are data, not translated text
    assert digits in box


def test_migration_adds_the_new_click_columns():
    text = open("alembic/versions/0009_click_audience_details.py", encoding="utf-8").read()
    for column in ("source", "browser", "os", "country", "city", "visitor"):
        assert f"'{column}'" in text and hasattr(Click, column)
    assert "down_revision = '0008'" in text


def test_busiest_time_tile_shows_the_weekday_and_the_hour(alice, app):
    make(alice)
    when = datetime(2026, 11, 13, 14, 40, tzinfo=timezone.utc)  # Friday 20:10 in India
    link_id = add(app, when, visitor="a")
    alice.cookies.set("tz", "Asia/Kolkata")
    box = audience_box(alice.get(f"/dashboard/links/{link_id}?range=365").text)
    assert 'stat-value">Friday<' in box and "20:00–21:00" in box
