"""Analytics charts: bar / line / area drawn as SVG, today by hour and day by day."""

import re
from datetime import timedelta
from pathlib import Path

import pytest

from app.charts import KINDS, chart_set, chart_svg, nice_max
from app.i18n import native_digits, translate
from app.models import Click, Link, utcnow

APP = Path(__file__).resolve().parent.parent / "app"
ONE = [{"name": None, "color": "var(--accent)"}]


def one(values):
    return [{**ONE[0], "values": values}]


# ---- the drawing -----------------------------------------------------------------------------


@pytest.mark.parametrize("peak, top", [
    (0, 4), (1, 4), (4, 4), (5, 8), (9, 12), (13, 16), (21, 24), (33, 40), (100, 120), (250, 320),
])
def test_the_y_axis_top_is_round_and_splits_into_whole_steps(peak, top):
    assert nice_max(peak) == top and top >= peak and top % 4 == 0


def test_every_kind_draws_the_same_axes_and_hover_areas():
    labels = ["a", "b", "c", "d", "e"]
    for kind in KINDS:
        svg = str(chart_svg(kind, labels, one([0, 3, 5, 2, 1]), aria="Clicks"))
        assert svg.startswith("<svg") and svg.endswith("</svg>")
        assert f"chart-{kind}" in svg and 'role="img"' in svg and 'aria-label="Clicks"' in svg
        assert svg.count('class="c-grid"') == 5  # 0 and four steps
        assert svg.count('class="c-hit"') == 5  # one tooltip area per position
        for label in labels:
            assert f">{label}</text>" in svg


def test_bar_draws_a_bar_and_a_number_for_each_busy_position_only():
    svg = str(chart_svg("bar", list("abcde"), one([0, 3, 5, None, 1]), aria="x"))
    assert svg.count('class="c-bar"') == 3  # the 0 and the not-yet-happened draw nothing
    assert svg.count('class="c-val"') == 3
    assert "<circle" not in svg and 'class="c-line"' not in svg


def test_line_has_ringed_dots_and_area_adds_a_fill_under_it():
    values = one([1, 4, 2, 6])
    line = str(chart_svg("line", list("abcd"), values, aria="x"))
    area = str(chart_svg("area", list("abcd"), values, aria="x"))
    assert line.count('class="c-dot"') == 4 and line.count('class="c-line"') == 1
    assert 'class="c-area"' not in line
    assert area.count('class="c-area"') == 1 and area.count('class="c-line"') == 1
    assert "Z" in re.search(r'class="c-area" d="([^"]+)"', area).group(1)  # a closed shape


def test_the_future_is_not_drawn_and_a_gap_splits_the_line():
    svg = str(chart_svg("line", list("abcdef"), one([2, 3, None, 1, 4, None]), aria="x"))
    assert svg.count('class="c-line"') == 2  # two separate stretches
    assert svg.count('class="c-dot"') == 4
    assert svg.count('class="c-hit"') == 4  # nothing to hover where nothing is known


def test_tooltips_one_series_and_many():
    single = str(chart_svg("bar", ["09", "10"], one([2, 0]), aria="x",
                           tip_labels=["09 Nov", "10 Nov"]))
    assert "<title>09 Nov: 2</title>" in single and "<title>10 Nov: 0</title>" in single
    many = str(chart_svg("line", ["a", "b"], [
        {"name": "one1", "color": "#0072B2", "values": [2, 0]},
        {"name": "two2", "color": "#E69F00", "values": [1, 5]},
    ], aria="x", tip_labels=["Mon", "Tue"]))
    assert "<title>Mon\none1: 2\ntwo2: 1</title>" in many
    assert "<title>Tue\none1: 0\ntwo2: 5</title>" in many
    assert "#0072B2" in many and "#E69F00" in many  # each link keeps its own colour


def test_all_series_share_one_scale():
    svg = str(chart_svg("bar", ["a"], [
        {"name": "x", "color": "red", "values": [2]},
        {"name": "y", "color": "blue", "values": [40]},
    ], aria="x"))
    assert ">40</text>" in svg  # the axis reaches the larger link's number
    heights = [float(h) for h in re.findall(r'class="c-bar"[^>]*height="([\d.]+)"', svg)]
    assert heights[1] > heights[0] * 10


def test_digits_follow_the_language_and_text_is_escaped():
    hi = lambda v: native_digits("hi", v)  # noqa: E731
    svg = str(chart_svg("bar", ["०९"], one([7]), aria="Clicks", num=hi))
    texts = re.findall(r'<text class="c-(?:text|val)"[^>]*>([^<]*)</text>', svg)
    assert texts and all(not re.search("[0-9]", t) for t in texts)
    evil = str(chart_svg("bar", ["<b>"], [{"name": "<i>", "color": "red", "values": [1]}],
                         aria='"><script>alert(1)</script>', tip_labels=["<&>"]))
    assert "<script>" not in evil and "&lt;script&gt;" in evil and "&lt;&amp;&gt;" in evil


def test_unknown_kind_is_a_programming_error():
    with pytest.raises(KeyError):
        chart_svg("pie", ["a"], one([1]), aria="x")
    assert set(chart_set(["a"], one([1]), aria="x")) == set(KINDS)


# ---- the pages -------------------------------------------------------------------------------


def make(client, slug="lnk"):
    data = {"original_url": "https://example.com/p", "slug": slug}
    return client.post("/dashboard/links", data=data)


def link_id(app, slug="lnk"):
    with app.state.session_factory() as db:
        return db.query(Link).filter_by(slug=slug).one().id


def click_now(app, slug="lnk", hours_ago=0):
    with app.state.session_factory() as db:
        link = db.query(Link).filter_by(slug=slug).one()
        when = utcnow() - timedelta(hours=hours_ago)
        db.add(Click(link_id=link.id, clicked_at=when, device="desktop"))
        link.click_count += 1
        db.commit()


def section(page: str) -> str:
    start = page.index('<section class="analytics">')
    return page[start:page.index("</section>", start)]


def test_analytics_page_has_a_type_switch_and_two_charts(alice, app):
    make(alice)
    box = section(alice.get(f"/dashboard/links/{link_id(app)}").text)
    assert re.findall(r'class="ct ct-(\w+)" type="radio"', box) == ["bar", "line", "area"]
    assert 'id="ct-bar" value="bar" checked' in box  # Bar is the default (works without JavaScript)
    assert re.findall(r'<label class="tab-(\w+)"', box) == ["bar", "line", "area"]
    assert 'role="radiogroup" aria-label="Chart type"' in box
    cards = box.split('class="chart-card"')[1:]
    assert len(cards) == 2
    assert "Clicks today, hour by hour" in cards[0] and "Clicks per day" in cards[1]
    for card in cards:  # every chart exists in all three kinds
        assert [k for k in KINDS if f"chart-{k}" in card] == list(KINDS)
    assert box.index("Clicks today") < box.index("Clicks per day")  # hourly first, then day by day


def test_hourly_chart_counts_todays_clicks_and_stops_at_now(alice, app):
    make(alice)
    click_now(app)
    click_now(app)
    page = alice.get(f"/dashboard/links/{link_id(app)}").text
    hourly = section(page).split('class="chart-card"')[1]
    bar = hourly[hourly.index("chart-bar"):hourly.index("chart-line")]
    hour = utcnow().hour
    assert f"<title>{hour:02d}:00: 2</title>" in bar  # both clicks landed in this hour
    hits = bar.count('class="c-hit"')
    assert hour + 1 <= hits <= hour + 2  # hours that have not happened yet are not drawn
    assert "2 clicks today" in hourly and "No clicks yet today." not in hourly


def test_hourly_chart_says_so_when_there_are_no_clicks_today(alice, app):
    make(alice)
    page = alice.get(f"/dashboard/links/{link_id(app)}").text
    assert "No clicks yet today." in section(page)


def test_yesterdays_clicks_are_in_the_daily_chart_not_the_hourly_one(alice, app):
    make(alice)
    click_now(app, hours_ago=30)
    page = alice.get(f"/dashboard/links/{link_id(app)}").text
    cards = section(page).split('class="chart-card"')[1:]
    assert "No clicks yet today." in cards[0]
    assert re.search(r"<title>\d\d \w{3}: 1</title>", cards[1])


def test_daily_chart_has_14_days(alice, app):
    make(alice)
    page = alice.get(f"/dashboard/links/{link_id(app)}").text
    daily = section(page).split('class="chart-card"')[2]
    bar = daily[daily.index("chart-bar"):daily.index("chart-line")]
    assert bar.count('class="c-hit"') == 14


def test_the_choice_is_remembered_with_a_tiny_script_but_works_without_it(alice, app):
    make(alice)
    box = section(alice.get(f"/dashboard/links/{link_id(app)}").text)
    assert "localStorage.getItem('chartType')" in box and "setItem('chartType'" in box
    assert "^(bar|line|area)$" in box  # only a known value is ever used
    css = (APP / "static" / "style.css").read_text(encoding="utf-8")
    assert ".chart-card figure { display: none;" in css  # CSS shows only the selected kind
    for kind in KINDS:
        assert f".ct-{kind}:checked ~ .charts .p-{kind}" in css


def test_compare_page_has_the_same_two_charts_for_every_link(alice, app):
    make(alice, "one1")
    make(alice, "two2")
    click_now(app, "one1")
    click_now(app, "two2")
    click_now(app, "two2")
    box = section(alice.get("/dashboard/links/compare?ids=1&ids=2").text)
    assert re.findall(r'class="ct ct-(\w+)"', box) == ["bar", "line", "area"]
    cards = box.split('class="chart-card"')[1:]
    assert "Clicks today, hour by hour" in cards[0] and "Clicks per day" in cards[1]
    hour = utcnow().hour
    tip = re.search(rf"<title>{hour:02d}:00\n([^<]*)</title>", cards[0]).group(1).split("\n")
    assert sorted(tip) == ["one1: 1", "two2: 2"]  # each link's number in one tooltip
    assert "3 clicks today" in cards[0]


def test_day_page_uses_the_same_switch_and_charts(alice, app):
    make(alice)
    with app.state.session_factory() as db:
        db.query(Link).one().created_at = utcnow() - timedelta(days=3)
        db.commit()
    click_now(app, hours_ago=26)
    day = (utcnow() - timedelta(hours=26)).date().isoformat()
    page = alice.get(f"/dashboard/links/{link_id(app)}/day/{day}").text
    box = section(page)
    assert re.findall(r'class="ct ct-(\w+)"', box) == ["bar", "line", "area"]
    assert box.count('class="chart-card"') == 1 and "Clicks per hour" in box
    assert box.count('<svg class="chart-svg') == 3


@pytest.mark.parametrize("lang", ["hi", "gu"])
def test_chart_text_is_translated_with_native_digits(alice, app, lang):
    make(alice)
    click_now(app)
    alice.post("/language", data={"lang": lang, "next": "/"})
    box = section(alice.get(f"/dashboard/links/{link_id(app)}").text)
    for english in ("Chart type", "Clicks today, hour by hour", "No clicks yet today."):
        assert english not in box
    assert translate(lang, "Clicks today, hour by hour") in box
    labels = re.findall(r'<label class="tab-\w+"[^>]*>.*?<span>([^<]+)</span>', box, re.S)
    assert labels == [translate(lang, k) for k in ("Bar", "Line", "Area")]
    texts = re.findall(r'<text class="c-(?:text|val)"[^>]*>([^<]*)</text>', box)
    assert texts and all(not re.search("[0-9]", t) for t in texts)
