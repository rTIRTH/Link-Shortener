"""The Share button on the dashboard toolbar and its pop-up (Copy link, Download QR, apps, More)."""

import re
from pathlib import Path

import pytest

from app.i18n import js_data, translate
from app.models import Link

APP = Path(__file__).resolve().parent.parent / "app"
URL = "https://example.com/page"


def make(client, slug="lnk"):
    return client.post("/dashboard/links", data={"original_url": URL, "slug": slug})


def toolbar(page: str) -> str:
    start = page.index('<form method="post" id="bulk"')
    return page[start:page.index("</form>", start)]


def dialog(page: str) -> str:
    start = page.index('<dialog id="share-dialog"')
    return page[start:page.index("</dialog>", start)]


def test_share_sits_after_stats_in_one_group_and_starts_disabled(alice):
    make(alice)
    bar = toolbar(alice.get("/dashboard").text)
    group = bar[bar.index('class="selection-actions"'):]
    labels = re.findall(r'id="(edit|stats|share)-selected"', group)
    assert labels == ["edit", "stats", "share"]  # Edit, Stats, Share: left to right
    share = re.search(r'<button[^>]*id="share-selected"[^>]*>', group).group(0)
    assert 'class="btn small ghost fill"' in share  # same look as Edit and Stats
    assert 'type="button"' in share and "disabled" in share  # opens a pop-up; needs a selection
    assert group.index("Edit") < group.index("Stats") < group.index(">Share<")
    assert "QR download uses" not in bar.replace('title="QR download uses', "")  # no text
    assert bar.index("Export CSV") < bar.index('class="selection-actions"')  # then the group


def test_each_row_carries_what_the_popup_needs(alice, app):
    make(alice, "one1")
    make(alice, "two2")
    alice.post("/dashboard/links/2/toggle", data={"active": "0"})
    page = alice.get("/dashboard").text
    boxes = re.findall(r'<input type="checkbox" name="ids"[^>]*class="pick"[^>]*>', page)
    assert len(boxes) == 2
    by_slug = {re.search(r'data-slug="([^"]+)"', b).group(1): b for b in boxes}
    one = by_slug["one1"]
    assert 'data-url="http://testserver/alice/one1"' in one and 'data-id="1"' in one
    assert 'data-status="active"' in one
    assert 'data-status="inactive"' in by_slug["two2"]


def test_popup_has_copy_and_qr_on_top_then_apps_then_more(alice):
    make(alice)
    box = dialog(alice.get("/dashboard").text)
    top = box[box.index('class="sd-top"'):box.index('id="share-status"')]
    assert top.index("Copy link") < top.index("Download QR")  # the two buttons on top
    apps = box[box.index('id="share-apps"'):box.index('id="share-extra"')]
    order = re.findall(r'data-app="(\w+)"|id="(share-more)"', apps)
    names = [a or b for a, b in order]
    assert names == ["whatsapp", "telegram", "gmail", "email", "facebook", "x", "linkedin",
                     "share-more"]
    for label in ("WhatsApp", "Gmail", "Telegram", "More"):
        assert label in apps
    extra = box[box.index('id="share-extra"'):]
    assert re.findall(r'data-app="(\w+)"', extra) == ["reddit", "pinterest", "tumblr", "line"]
    assert "hidden" in extra[:60]  # only shown when the browser has no share sheet of its own


def test_popup_is_accessible(alice):
    make(alice)
    box = dialog(alice.get("/dashboard").text)
    assert 'aria-labelledby="share-title"' in box and 'id="share-title"' in box
    assert 'aria-label="Close"' in box
    assert 'aria-label="Share via WhatsApp"' in box and 'aria-label="Share via Gmail"' in box
    assert 'aria-live="polite"' in box  # "Copied!" is announced
    assert 'aria-controls="share-extra"' in box and 'aria-expanded="false"' in box
    assert 'rel="noopener noreferrer"' in box  # app links must not get access to this page
    assert 'readonly' in box  # the link box cannot be edited by accident


def test_popup_and_script_only_when_there_are_links(alice):
    empty = alice.get("/dashboard").text
    assert "share-dialog" not in empty and "id=\"share-selected\"" not in empty
    make(alice)
    page = alice.get("/dashboard").text
    assert "share-dialog" in page
    assert re.search(r'<script src="/static/share\.js\?v=[^"]+" defer></script>', page)


def test_the_script_is_served_and_builds_the_app_addresses():
    js = (APP / "static" / "share.js").read_text(encoding="utf-8")
    for address in ("https://wa.me/?text=", "https://t.me/share/url", "https://mail.google.com/mail/",
                    "mailto:?subject=", "https://www.facebook.com/sharer/sharer.php",
                    "https://x.com/intent/post", "https://www.linkedin.com/sharing/share-offsite/"):
        assert address in js
    assert "navigator.share" in js and "navigator.clipboard" in js
    assert "encodeURIComponent" in js  # the link is encoded before it goes into an address
    assert "/qr.png?download=1" in js  # Download QR uses the existing QR route


def test_share_js_is_served(client):
    r = client.get("/static/share.js")
    assert r.status_code == 200 and "javascript" in r.headers["content-type"]


def test_qr_route_used_by_the_popup_works(alice):
    make(alice)
    with alice.app.state.session_factory() as db:
        link_id = db.query(Link).one().id
    r = alice.get(f"/dashboard/links/{link_id}/qr.png?download=1")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert "attachment" in r.headers["content-disposition"]


@pytest.mark.parametrize("lang", ["hi", "gu"])
def test_popup_is_translated(alice, lang):
    make(alice)
    alice.post("/language", data={"lang": lang, "next": "/"})
    page = alice.get("/dashboard").text
    box = dialog(page)
    for english in ("Share link", "Copy link", "Download QR", "Share via", "Check out this link",
                    "not active right now"):
        assert english not in box, english
    assert translate(lang, "Copy link") in box and translate(lang, "Download QR") in box
    assert f">{translate(lang, 'Share')}</button>" in toolbar(page)
    assert translate(lang, "Select one link to share it.") in toolbar(page)
    assert "WhatsApp" in box and "Gmail" in box  # app names are brand names: left as they are
    ui = js_data(lang)["ui"]
    assert ui["share_copied"] == translate(lang, "Copied!") != "Copied!"
    assert ui["share_copy_failed"] != "Could not copy automatically. Select the link and copy it."


def test_english_strings_for_the_script():
    ui = js_data("en")["ui"]
    assert ui["share_copied"] == "Copied!"
    assert ui["share_copy_failed"].startswith("Could not copy")


def test_layout_rules_keep_the_three_buttons_together():
    css = (APP / "static" / "style.css").read_text(encoding="utf-8")
    assert ".selection-actions {" in css and "flex: 1 1 0" in css  # equal widths
    assert ".share-dialog" in css and ".sd-apps" in css and "repeat(4, 1fr)" in css


def test_toolbar_has_no_hint_text_but_the_qr_button_explains_itself(alice):
    make(alice)
    bar = toolbar(alice.get("/dashboard").text)
    assert not re.search(r"<small[^>]*>[^<]*QR download uses", bar)  # no line of text on the page
    qr = re.search(r'<button[^>]*qr\.zip"[^>]*>', bar).group(0)
    assert 'title="QR download uses the selected links, or all links if none are selected."' in qr
