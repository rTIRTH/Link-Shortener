"""Campaign tracking tags (UTM) added to a link's destination."""

import csv
import io
import re

import pytest

from app import features
from app.models import Link
from app.utm import MAX_UTM_LENGTH, clean_value, merge, split_utm, with_utm

BASE = "https://example.com/sale"


def make(client, slug="lnk", url=BASE, **extra):
    return client.post("/dashboard/links", data={"original_url": url, "slug": slug, **extra})


def stored(app, slug="lnk"):
    with app.state.session_factory() as db:
        return db.query(Link).filter_by(slug=slug).one().original_url


def lid(app, slug="lnk"):
    with app.state.session_factory() as db:
        return db.query(Link).filter_by(slug=slug).one().id


def edit(client, app, url=BASE, boxes=True, slug="lnk", **fields):
    data = {"original_url": url, "password_action": "keep", **fields}
    if boxes:
        data["utm_box"] = "1"  # the edit page sends this along with its tracking boxes
    return client.post(f"/dashboard/links/{lid(app, slug)}/edit", data=data)


# ---- the helpers ----------------------------------------------------------------------------


def test_tags_are_split_out_of_an_address():
    clean, tags = split_utm("https://a.com/p?x=1&utm_source=Face%20book&UTM_medium=social&y=2#top")
    assert clean == "https://a.com/p?x=1&y=2#top"
    assert tags == {"utm_source": "Face book", "utm_medium": "social"}


def test_an_address_without_tags_is_returned_exactly_as_it_was():
    for url in ("https://a.com/", "https://a.com/p?x=1&y=a+b&z=%7E", "https://a.com/p?#x"):
        assert split_utm(url) == (url, {})
    assert with_utm("https://a.com/p?x=%7E", {}) == "https://a.com/p?x=%7E"


def test_tags_are_added_after_the_existing_query_and_before_the_fragment():
    out = with_utm("https://a.com/p?x=1#top", {"utm_campaign": "summer sale", "utm_source": "a&b"})
    assert out == "https://a.com/p?x=1&utm_source=a%26b&utm_campaign=summer%20sale#top"
    assert with_utm("https://a.com/", {"utm_source": "x"}) == "https://a.com/?utm_source=x"


def test_tags_always_come_in_the_standard_order_and_empty_ones_are_left_out():
    out = with_utm("https://a.com/", {"utm_content": "c", "utm_source": "s", "utm_term": ""})
    assert out == "https://a.com/?utm_source=s&utm_content=c"


def test_boxes_win_over_tags_typed_in_the_address():
    clean, tags = merge(
        "https://a.com/?utm_source=old&utm_term=t", {"utm_source": "new", "utm_medium": ""}
    )
    assert clean == "https://a.com/" and tags == {"utm_source": "new", "utm_term": "t"}


def test_values_are_cleaned_and_limited():
    assert clean_value("  summer   sale ") == "summer sale" and clean_value(None) == ""
    assert clean_value("x" * MAX_UTM_LENGTH) == "x" * MAX_UTM_LENGTH
    for bad in ("x" * (MAX_UTM_LENGTH + 1), "a\x00b"):
        with pytest.raises(ValueError, match="up to 100 characters"):
            clean_value(bad)


def test_split_and_join_are_inverse():
    tags = {"utm_source": "a b", "utm_medium": "m&n", "utm_campaign": "ü"}
    url = with_utm("https://a.com/p?x=1", tags)
    assert split_utm(url) == ("https://a.com/p?x=1", tags)


# ---- creating --------------------------------------------------------------------------------


def test_the_boxes_are_added_to_the_destination(alice, app):
    make(alice, utm_source="instagram", utm_medium="social", utm_campaign="summer sale")
    expected = f"{BASE}?utm_source=instagram&utm_medium=social&utm_campaign=summer%20sale"
    assert stored(app) == expected


def test_the_short_link_sends_visitors_to_the_tagged_address(alice, app):
    make(alice, utm_source="instagram")
    r = alice.get("/alice/lnk")
    assert r.status_code == 302 and r.headers["location"] == f"{BASE}?utm_source=instagram"


def test_no_boxes_means_the_address_is_untouched(alice, app):
    make(alice, url="https://example.com/a?x=1&y=a+b")
    assert stored(app) == "https://example.com/a?x=1&y=a+b"


def test_tags_typed_into_the_address_are_kept(alice, app):
    make(alice, url=f"{BASE}?utm_source=email&ref=1")
    assert stored(app) == f"{BASE}?ref=1&utm_source=email"  # moved to the end, in order


def test_a_box_beats_the_same_tag_in_the_address(alice, app):
    make(alice, url=f"{BASE}?utm_source=old", utm_source="new", utm_medium="m")
    assert stored(app) == f"{BASE}?utm_source=new&utm_medium=m"


def test_a_value_that_is_too_long_is_refused(alice, app):
    make(alice, utm_source="x" * 101)
    assert "up to 100 characters" in alice.get("/dashboard").text
    with app.state.session_factory() as db:
        assert db.query(Link).count() == 0


def test_the_finished_address_must_still_be_a_valid_length(alice, app):
    make(alice, url=BASE + "?q=" + "a" * 2000, utm_campaign="b" * 100, utm_source="c" * 100)
    with app.state.session_factory() as db:
        assert db.query(Link).count() == 0
    assert "too long" in alice.get("/dashboard").text


def test_the_export_shows_the_real_destination(alice):
    make(alice, utm_campaign="x")
    rows = list(csv.DictReader(io.StringIO(alice.get("/dashboard/links/export.csv").text)))
    assert rows[0]["original_url"] == f"{BASE}?utm_campaign=x"


# ---- the create form -----------------------------------------------------------------------------


def test_the_create_form_has_the_boxes_and_the_live_preview_hook(alice):
    page = alice.get("/dashboard").text
    for key in ("utm_source", "utm_medium", "utm_campaign"):
        assert f'name="{key}"' in page and f'data-utm-input="{key}"' in page
    assert "utm_term" not in page  # term and content are on the Edit page
    assert "data-utm-scope" in page and "data-utm-url" in page and "/static/utm.js" in page
    assert "Campaign tracking (UTM)" in page and "Visitors will land on:" in page


def test_the_script_is_served(alice):
    js = alice.get("/static/utm.js")
    assert js.status_code == 200 and "utm_source" in js.text


# ---- the edit page ---------------------------------------------------------------------------


def test_the_edit_page_shows_the_address_without_its_tags_and_the_tags_in_boxes(alice, app):
    make(alice, utm_source="instagram")
    edit(alice, app, utm_source="instagram", utm_term="kids toys")  # term is an Edit page box
    page = alice.get(f"/dashboard/links/{lid(app)}/edit").text
    assert f'name="original_url" value="{BASE}"' in page  # clean
    assert 'name="utm_source" maxlength="100" autocomplete="off" value="instagram"' in page
    assert 'name="utm_term" maxlength="100" autocomplete="off" value="kids toys"' in page
    assert f"{BASE}?utm_source=instagram&amp;utm_term=kids%20toys" in page  # the final address
    for key in ("utm_medium", "utm_campaign", "utm_term", "utm_content"):
        assert f'name="{key}"' in page


def test_saving_rebuilds_the_address_from_the_boxes(alice, app):
    make(alice, utm_source="instagram")
    edit(alice, app, utm_source="facebook", utm_content="banner")
    assert stored(app) == f"{BASE}?utm_source=facebook&utm_content=banner"


def test_clearing_every_box_removes_the_tags(alice, app):
    make(alice, utm_source="instagram", utm_medium="social")
    edit(alice, app)
    assert stored(app) == BASE


def test_the_form_without_the_boxes_keeps_the_tags(alice, app):
    make(alice, utm_source="instagram")
    edit(alice, app, boxes=False)
    assert stored(app) == f"{BASE}?utm_source=instagram"


def test_changing_the_tags_is_written_in_the_activity_log(alice, app):
    make(alice, utm_source="a")
    edit(alice, app, utm_source="b")
    page = alice.get(f"/dashboard/links/{lid(app)}").text
    assert "Destination changed" in page and "utm_source=b" in page


def test_saving_the_same_tags_again_is_not_a_change(alice, app):
    make(alice, utm_source="a")
    edit(alice, app, utm_source="a")
    assert "Destination changed" not in alice.get(f"/dashboard/links/{lid(app)}").text


# ---- the paid-plan gate ------------------------------------------------------------------------


def test_locked_tracking_boxes_are_disabled_and_cannot_be_posted(alice, app, monkeypatch):
    make(alice, "one", utm_source="x")
    monkeypatch.setattr(features, "PAID", frozenset({"utm"}))
    page = alice.get("/dashboard").text
    assert re.search(r'name="utm_source"[^>]*disabled', page)  # the box is there but locked
    assert page.count("disabled") >= 3 and "paid plan" in page
    make(alice, "two", utm_source="y")
    assert "paid plan" in alice.get("/dashboard").text
    with app.state.session_factory() as db:
        assert db.query(Link).filter_by(slug="two").count() == 0
    make(alice, "three")  # a plain link is unaffected
    assert stored(app, "three") == BASE


def test_a_locked_edit_keeps_the_tags_and_refuses_changes(alice, app, monkeypatch):
    make(alice, utm_source="x")
    monkeypatch.setattr(features, "PAID", frozenset({"utm"}))
    page = alice.get(f"/dashboard/links/{lid(app)}/edit").text
    assert 'name="utm_box"' not in page and "paid plan" in page
    edit(alice, app, url=BASE + "/new", boxes=False)  # what the locked page really posts
    assert stored(app) == f"{BASE}/new?utm_source=x"  # the address changed, the tag stayed
    edit(alice, app, url=BASE + "?utm_source=hacked", boxes=False)  # typing a tag by hand
    assert stored(app) == f"{BASE}/new?utm_source=x"
    edit(alice, app, boxes=True, utm_source="hacked")  # posting the boxes by hand
    assert stored(app) == f"{BASE}/new?utm_source=x"


@pytest.mark.parametrize("lang, word", [("hi", "कैंपेन ट्रैकिंग"), ("gu", "કૅમ્પેઇન ટ્રૅકિંગ")])
def test_the_tracking_screens_render_in_every_language(alice, app, lang, word):
    make(alice, utm_source="x")
    alice.post("/language", data={"lang": lang, "next": "/"})
    assert word in alice.get("/dashboard").text
    assert word in alice.get(f"/dashboard/links/{lid(app)}/edit").text
