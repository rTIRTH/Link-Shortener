"""Hindi and Gujarati pages show their own digits (०-९ / ૦-૯). English keeps 0-9."""

import re
from datetime import date, timedelta

import pytest

from app.i18n import (
    ascii_digits,
    format_date,
    js_data,
    native_digits,
    translate,
    translate_html,
    translate_plural,
)
from app.models import Click, Link, utcnow
from app.utils import parse_moment

HI, GU = "०१२३४५६७८९", "૦૧૨૩૪૫૬૭૮૯"
NATIVE = {"hi": re.compile("[०-९]"), "gu": re.compile("[૦-૯]")}


def make(client, slug="lnk", **fields):
    return client.post(
        "/dashboard/links",
        data={"original_url": "https://example.com/page", "slug": slug, **fields},
    )


def use(client, lang):
    client.post("/language", data={"lang": lang, "next": "/"})


# ---- the helpers ----------------------------------------------------------------------------


def test_native_digits_and_back():
    assert native_digits("hi", "2026-11-09 10:05") == "२०२६-११-०९ १०:०५"
    assert native_digits("gu", 1234567890) == "૧૨૩૪૫૬૭૮૯૦"
    assert native_digits("en", 1234567890) == "1234567890"
    assert native_digits("fr", "12") == "12"  # an unknown language is left alone
    for lang, digits in (("hi", HI), ("gu", GU)):
        assert native_digits(lang, "0123456789") == digits
        assert ascii_digits(digits) == "0123456789"
    assert ascii_digits("12/10/2026, 09:30 PM") == "12/10/2026, 09:30 PM"
    assert ascii_digits("१२/१०/૨૦૨૬") == "12/10/2026"  # mixed scripts are fine too


def test_dates_follow_the_language():
    d = date(2026, 11, 9)
    assert format_date(d, "en") == "09 Nov"
    assert format_date(d, "en", year=True) == d.strftime("%d %b %Y")  # as it was before
    assert format_date(d, "hi", year=True) == "०९ नव॰ २०२६"
    assert format_date(d, "gu") == "૦૯ નવે"
    for month in range(1, 13):  # every month has a name in every language
        for lang in ("en", "hi", "gu"):
            assert format_date(date(2026, month, 1), lang)


def test_whole_numbers_become_native_but_text_does_not():
    assert translate_plural("hi", "{n} link", "{n} links", 12) == "१२ लिंक"
    assert translate_plural("gu", "{n} click", "{n} clicks", 1) == "૧ ક્લિક"
    assert translate_plural("en", "{n} link", "{n} links", 12) == "12 links"
    # a slug or a code is text: its digits are NOT changed
    assert "a1b2c3" in translate("hi", "Download QR code for {slug}", slug="a1b2c3")
    assert "a1b2c3" in translate_html("hi", "Download QR code for {slug}", slug="a1b2c3")
    # True/False are not numbers
    assert translate("en", "{n}", n=True) == "True"


def test_digits_written_inside_a_translation_are_converted():
    assert "४-७२" in translate("hi", "4-72 characters")
    assert "૪-૭૨" in translate("gu", "4-72 characters")
    assert translate("en", "4-72 characters") == "4-72 characters"
    # no translation yet: the English text is shown exactly as given
    assert translate("hi", "Order 66 is not translated") == "Order 66 is not translated"


def test_js_gets_the_digits_to_use():
    assert js_data("hi")["digits"] == HI
    assert js_data("gu")["digits"] == GU
    assert js_data("en")["digits"] == ""
    assert not re.search("[0-9]", js_data("hi")["ui"]["bad_date"].replace("{example}", ""))


@pytest.mark.parametrize("typed", [
    "११/१०/२०२६, ०९:३०:१५ PM", "11/10/2026, 09:30:15 PM", "૧૧/૧૦/૨૦૨૬, ૦૯:૩૦:૧૫ PM",
])
def test_typed_native_digits_are_understood_without_javascript(typed):
    moment = parse_moment("", typed)
    assert (moment.year, moment.month, moment.day) == (2026, 10, 11)
    assert (moment.hour, moment.minute, moment.second) == (21, 30, 15)


def test_the_forms_hidden_utc_value_can_also_be_native():
    assert parse_moment("२०२६-१०-११T२१:३०:००Z", "").hour == 21


# ---- the pages -------------------------------------------------------------------------------


def stamp_clicks(app, slug="lnk", days_ago=1):
    with app.state.session_factory() as db:
        link = db.query(Link).filter_by(slug=slug).one()
        link.created_at = utcnow() - timedelta(days=4)
        when = (utcnow() - timedelta(days=days_ago)).replace(hour=14, minute=5)
        for _ in range(3):
            db.add(Click(link_id=link.id, clicked_at=when, device="mobile", referrer="x.com"))
        link.click_count = 3
        db.commit()
        return link.id


@pytest.mark.parametrize("lang", ["hi", "gu"])
def test_dashboard_numbers_are_native_but_the_short_link_is_not(alice, app, lang):
    make(alice, "a1b2c3")
    stamp_clicks(app, "a1b2c3")
    use(alice, lang)
    page = alice.get("/dashboard").text
    assert f'<td class="num">{native_digits(lang, 3)}</td>' in page
    assert "/alice/a1b2c3" in page  # the address you copy must stay exactly as it is
    assert "https://example.com/page" in page
    # "1 link · 3 total clicks" in the language, with its digits
    assert translate_plural(lang, "{n} link", "{n} links", 1) in page
    assert translate_plural(lang, "{n} total click", "{n} total clicks", 3) in page


@pytest.mark.parametrize("lang", ["hi", "gu"])
def test_stats_page_uses_native_digits_and_month_names(alice, app, lang):
    make(alice, "a1b2c3")
    lid = stamp_clicks(app, "a1b2c3")
    use(alice, lang)
    page = alice.get(f"/dashboard/links/{lid}").text
    yesterday = utcnow().date() - timedelta(days=1)
    # activity log row and the chart tooltip for the day with the clicks
    assert format_date(yesterday, lang, year=True) in page
    assert f"{format_date(yesterday, lang)}: {native_digits(lang, 3)}" in page
    assert f'<td class="num">{native_digits(lang, 3)}</td>' in page
    assert re.search(r"Nov|Oct|Dec", re.sub(r"<[^>]+>|a1b2c3|testserver", "", page)) is None
    # fallback time text, shown until the browser script swaps in local time
    assert re.search(r"<time[^>]*>[^<]*UTC</time>", page)
    for text in re.findall(r"<time[^>]*>([^<]*)</time>", page):
        assert not re.search("[0-9]", text) and NATIVE[lang].search(text)


@pytest.mark.parametrize("lang", ["hi", "gu"])
def test_day_page_hours_and_busiest_hour_are_native(alice, app, lang):
    make(alice, "a1b2c3")
    lid = stamp_clicks(app, "a1b2c3")
    use(alice, lang)
    day = (utcnow() - timedelta(days=1)).date().isoformat()
    page = alice.get(f"/dashboard/links/{lid}/day/{day}").text
    assert f'title="{native_digits(lang, "14:00")} · {native_digits(lang, 3)}"' in page
    assert native_digits(lang, "14:00–15:00") in page
    labels = re.findall(r'<span class="lbl">([^<]*)</span>', page)
    assert len(labels) == 24 and all(not re.search("[0-9]", x) for x in labels)


@pytest.mark.parametrize("lang", ["hi", "gu"])
def test_compare_page_is_native(alice, app, lang):
    make(alice, "one1")
    make(alice, "two2")
    stamp_clicks(app, "one1")
    use(alice, lang)
    page = alice.get("/dashboard/links/compare?ids=1&ids=2").text
    assert f"{format_date(utcnow().date(), lang)}: " in page
    labels = re.findall(r'<span class="lbl">([^<]*)</span>', page)
    assert len(labels) == 14 and all(NATIVE[lang].search(x) for x in labels)
    assert f'<td class="num">{native_digits(lang, 3)}</td>' in page


@pytest.mark.parametrize("lang", ["hi", "gu"])
def test_photo_editor_start_values_are_native(alice, lang):
    use(alice, lang)
    page = alice.get("/account").text
    assert f">{native_digits(lang, 100)}%</span>" in page
    assert f">{native_digits(lang, 0)}&deg;</span>" in page


@pytest.mark.parametrize("lang", ["hi", "gu"])
def test_flash_and_error_messages_with_numbers_are_native(alice, app, lang):
    use(alice, lang)
    for i in range(9):
        make(alice, f"link{i}")
    ids = "&".join(f"ids={i}" for i in range(1, 10))
    alice.get("/dashboard/links/compare?" + ids)  # "up to 8 links at a time"
    page = alice.get("/dashboard").text
    assert translate(lang, "You can compare up to {n} links at a time.", n=8) in page


def test_english_is_unchanged(alice, app):
    make(alice, "a1b2c3")
    lid = stamp_clicks(app, "a1b2c3")
    for url in ("/dashboard", f"/dashboard/links/{lid}"):
        page = alice.get(url).text
        assert not re.search("[०-९૦-૯]", page)
    assert "1 link · 3 total clicks" in alice.get("/dashboard").text
    yesterday = utcnow().date() - timedelta(days=1)
    assert yesterday.strftime("%d %b %Y") in alice.get(f"/dashboard/links/{lid}").text


def test_the_edit_form_still_saves_a_schedule_typed_in_native_digits(alice, app):
    make(alice)
    with app.state.session_factory() as db:
        lid = db.query(Link).one().id
    r = alice.post(f"/dashboard/links/{lid}/edit", data={
        "original_url": "https://example.com/page",
        "starts_at": "", "starts_at_utc": "",
        "expires_at": "१५/१२/२०३०, ०९:३०:०० PM", "expires_at_utc": "",
    })
    assert r.status_code == 303
    with app.state.session_factory() as db:
        ends = db.query(Link).one().expires_at
    assert (ends.year, ends.month, ends.day, ends.hour) == (2030, 12, 15, 21)
