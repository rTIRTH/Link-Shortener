"""The logo: files, favicon, and the mark in the top bar."""

import io
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PIL import Image

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
SVG = "{http://www.w3.org/2000/svg}"
SVG_FILES = ["brand/logo-mark.svg", "brand/logo.svg", "brand/logo-dark.svg", "favicon.svg"]
GRADIENT = ("#5a7bff", "#8f5cf6")  # indigo to violet, the same family as the site's accents


def parse(name):
    return ET.fromstring((STATIC / name).read_text(encoding="utf-8"))


# ---- the files themselves ----------------------------------------------------------------


@pytest.mark.parametrize("name", SVG_FILES)
def test_the_svgs_are_clean_and_self_contained(name):
    text = (STATIC / name).read_text(encoding="utf-8")
    root = ET.fromstring(text)
    assert root.tag == SVG + "svg" and root.get("viewBox")
    banned = ("<script", "foreignObject", "<image", "javascript:", "onload", "<style", "@import")
    for danger in banned:
        assert danger not in text, (name, danger)
    assert "http://" not in text.replace("http://www.w3.org/2000/svg", "")
    assert "https://" not in text  # nothing is loaded from anywhere


@pytest.mark.parametrize("name", SVG_FILES)
def test_every_svg_uses_the_brand_gradient(name):
    text = (STATIC / name).read_text(encoding="utf-8")
    assert all(stop in text for stop in GRADIENT)


@pytest.mark.parametrize("name", ["brand/logo.svg", "brand/logo-dark.svg"])
def test_the_wordmark_is_drawn_as_shapes_so_no_font_is_needed(name):
    root = parse(name)
    assert root.find(f".//{SVG}text") is None
    assert len(root.findall(f"{SVG}path")) == 2  # "Link" and "Shortener"
    assert root.get("aria-label") == "Link Shortener" and root.get("role") == "img"
    width, height = float(root.get("width")), float(root.get("height"))
    assert 4 < width / height < 6  # a wide lockup


def test_the_light_and_dark_logos_differ_only_in_text_colour():
    light = (STATIC / "brand/logo.svg").read_text(encoding="utf-8")
    dark = (STATIC / "brand/logo-dark.svg").read_text(encoding="utf-8")
    assert light != dark
    assert re.sub(r'fill="#[0-9a-f]{6}"', "", light) == re.sub(r'fill="#[0-9a-f]{6}"', "", dark)


def test_the_favicon_ico_holds_the_usual_sizes():
    icon = Image.open(STATIC / "favicon.ico")
    assert icon.format == "ICO"
    assert {(16, 16), (32, 32), (48, 48)} <= set(icon.info["sizes"])


def test_the_touch_icon_is_a_square_png_without_transparent_corners():
    icon = Image.open(STATIC / "apple-touch-icon.png").convert("RGBA")
    assert icon.size == (180, 180)
    assert icon.getpixel((0, 0))[3] == 255 and icon.getpixel((179, 179))[3] == 255  # iOS rounds it


def test_the_favicon_svg_has_rounded_corners_and_the_icon_ico_too():
    assert parse("favicon.svg").find(f"{SVG}rect").get("rx") not in (None, "0")
    corner = Image.open(STATIC / "favicon.ico").convert("RGBA").getpixel((0, 0))
    assert corner[3] == 0  # transparent corner: the tile is rounded


# ---- served by the app ------------------------------------------------------------------------


@pytest.mark.parametrize("path, kind", [
    ("/static/favicon.svg", "image/svg+xml"),
    ("/static/brand/logo.svg", "image/svg+xml"),
    ("/static/brand/logo-dark.svg", "image/svg+xml"),
    ("/static/brand/logo-mark.svg", "image/svg+xml"),
    ("/static/apple-touch-icon.png", "image/png"),
])
def test_the_files_are_served_to_everyone(client, path, kind):
    r = client.get(path)
    assert r.status_code == 200 and r.headers["content-type"].startswith(kind)


def test_browsers_asking_for_favicon_ico_get_it(client):
    r = client.get("/favicon.ico")
    assert r.status_code == 200 and r.headers["content-type"] == "image/x-icon"
    assert r.content == (STATIC / "favicon.ico").read_bytes()
    assert "max-age" in r.headers["cache-control"]
    assert Image.open(io.BytesIO(r.content)).format == "ICO"


# ---- on the pages -------------------------------------------------------------------------------


def icon_links(page):
    return re.findall(r'<link rel="((?:apple-touch-)?icon)" href="([^"]+)"', page)


@pytest.mark.parametrize("path", ["/", "/login", "/register", "/guide"])
def test_every_page_declares_the_icons_and_they_all_load(client, path):
    page = client.get(path).text
    links = icon_links(page)
    assert [rel for rel, _ in links] == ["icon", "icon", "apple-touch-icon"]
    assert 'type="image/svg+xml"' in page and 'sizes="48x48"' in page
    for _rel, href in links:
        assert client.get(href).status_code == 200, href


def test_the_signed_in_pages_have_them_too(alice):
    for path in ("/dashboard", "/guide"):
        assert len(icon_links(alice.get(path).text)) == 3


def test_the_top_bar_shows_the_mark_before_the_name(client):
    page = client.get("/").text
    brand = re.search(r'<a class="brand" href="/">(.*?)</a>', page, re.S).group(1)
    assert brand.index("<img") < brand.index("<span>Link Shortener</span>")
    assert 'src="/static/brand/logo-mark.svg"' in brand
    assert 'alt=""' in brand  # decorative: the link is still named by its text
    assert 'width="30" height="30"' in brand  # no jump while it loads


@pytest.mark.parametrize("lang", ["hi", "gu"])
def test_the_name_is_not_translated_but_the_mark_stays(client, lang):
    client.cookies.set("lang", lang)
    page = client.get("/guide").text
    assert "<span>Link Shortener</span>" in page and "/static/brand/logo-mark.svg" in page


def test_the_mark_has_a_rule_so_it_never_stretches():
    css = (STATIC / "style.css").read_text(encoding="utf-8")
    assert re.search(r"\.brand-mark\s*\{[^}]*width:\s*30px[^}]*height:\s*30px", css)
    inline = re.search(r"\.brand-mark\s*\{[^}]*vertical-align", css)
    assert inline  # the mark sits inline, so the name keeps the text baseline
