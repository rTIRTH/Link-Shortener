"""Small things: two links that are now buttons, and a tighter top bar on narrow phones."""
import re
from pathlib import Path

import tinycss2

CSS = Path("app/static/style.css").read_text(encoding="utf-8")


def make(client, slug="lnk"):
    return client.post("/dashboard/links", data={
        "original_url": "https://example.com/" + slug, "slug": slug})


def blocks(selector):
    """The declarations of every top-level rule that lists `selector`."""
    found = []
    for rule in tinycss2.parse_stylesheet(CSS, skip_whitespace=True, skip_comments=True):
        if rule.type == "qualified-rule":
            names = [s.strip() for s in tinycss2.serialize(rule.prelude).split(",")]
            if selector in names:
                found.append(tinycss2.serialize(rule.content))
    return found


def media(query, containing):
    """The body of the @media block with this query that mentions `containing`."""
    for rule in tinycss2.parse_stylesheet(CSS, skip_whitespace=True, skip_comments=True):
        if rule.type == "at-rule" and rule.lower_at_keyword == "media" \
                and query in tinycss2.serialize(rule.prelude):
            body = tinycss2.serialize(rule.content)
            if containing in body:
                return body
    raise AssertionError(f"no @media {query} with {containing}")


# ---------- "Import many links from a CSV file" ----------

def test_the_csv_import_link_is_a_button(alice):
    make(alice)
    html = alice.get("/dashboard").text
    assert re.search(
        r'<a class="btn small ghost" href="/dashboard/links/import">Import many links from a '
        r'CSV file</a>', html)


def test_a_locked_import_is_not_a_button_but_still_says_why(alice, monkeypatch):
    from app import features
    monkeypatch.setattr(features, "PAID", frozenset({"csv_import"}))
    html = alice.get("/dashboard").text
    assert 'href="/dashboard/links/import"' not in html
    assert "This feature is part of a paid plan." in html


def test_the_button_has_room_around_it(alice):
    rule = " ".join(blocks(".import-hint"))
    assert "margin: 14px 2px 20px" in rule


# ---------- "Download QR as SVG" in the share pop-up ----------

def test_the_svg_download_is_a_button_in_the_popup(alice):
    make(alice)
    html = alice.get("/dashboard").text
    box = html[html.index('class="sd-top"'):html.index('id="share-status"')]
    link = re.search(r'<a [^>]*id="share-qr-svg"[^>]*>.*?</a>', box, re.S).group(0)
    assert "btn ghost has-icon sd-wide" in link and "download" in link
    assert "<svg" in link and "Download QR as SVG" in link   # an icon, and the same words
    assert '<p class="sd-note"><a' not in html                # no longer a plain text link


def test_the_svg_button_sits_below_the_other_two_across_the_full_width():
    assert "grid-column: 1 / -1" in " ".join(blocks(".sd-top .sd-wide"))


def test_the_script_still_finds_the_svg_button():
    js = Path("app/static/share.js").read_text(encoding="utf-8")
    assert "share-qr-svg" in js


# ---------- the top bar on narrow phones ----------

def test_the_name_never_breaks_onto_two_lines():
    assert "white-space: nowrap" in " ".join(blocks(".brand"))


def test_the_narrow_rules_only_change_size_and_spacing():
    narrow = media("max-width: 480px", ".brand")
    assert ".topbar" in narrow and ".brand" in narrow and ".modebtn" in narrow
    props = set(re.findall(r"([a-z-]+)\s*:", narrow))
    allowed = {"padding", "gap", "font-size", "width", "height", "margin-right", "vertical-align",
               "flex-wrap", "min-width"}
    assert props <= allowed, props - allowed                         # no colours, no layout moves


def test_the_bar_still_wraps_instead_of_overflowing():
    assert "flex-wrap: wrap" in " ".join(blocks(".topbar"))
    assert "flex-wrap: wrap" in media("max-width: 480px", ".brand")  # the links, if they must


def test_the_one_link_buttons_wrap_instead_of_pushing_the_page_wide():
    rule = " ".join(blocks(".selection-actions"))
    assert "flex-wrap: wrap" in rule and "max-width: 100%" in rule
    assert "flex: 0 0 auto" in rule                                  # still never stretched
