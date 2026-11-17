"""QR code style: colours, a logo in the centre, and PNG or SVG."""

import io
import re
import xml.etree.ElementTree as ET
import zipfile

import pytest
from PIL import Image
from sqlalchemy import inspect

from app import features
from app.models import Link
from app.qr import (
    DEFAULT_BG,
    DEFAULT_FG,
    MAX_LOGO_BYTES,
    MIN_CONTRAST,
    QrStyle,
    check_colors,
    contrast_ratio,
    parse_color,
    png_bytes,
    process_logo,
    svg_text,
)

URL = "https://link-shortener-tcom.onrender.com/tirth/9dHYwI"
NS = {"s": "http://www.w3.org/2000/svg"}


def picture(size=(300, 200), color=(200, 30, 30, 255), fmt="PNG"):
    buf = io.BytesIO()
    image = Image.new("RGBA" if fmt == "PNG" else "RGB", size, color if fmt == "PNG" else color[:3])
    image.save(buf, format=fmt)
    return buf.getvalue()


def make(client, slug="lnk"):
    return client.post("/dashboard/links", data={
        "original_url": "https://example.com/" + slug, "slug": slug})


def row(app, slug="lnk"):
    with app.state.session_factory() as db:
        link = db.query(Link).filter_by(slug=slug).one()
        return {"id": link.id, "fg": link.qr_fg, "bg": link.qr_bg, "logo": link.qr_logo}


def save(client, link_id, **fields):
    files = {}
    if "logo" in fields:
        files["logo"] = ("logo.png", fields.pop("logo"), "image/png")
    data = {"qr_fg": "#000000", "qr_bg": "#ffffff", **fields}
    return client.post(f"/dashboard/links/{link_id}/qr-style", data=data, files=files or None)


def decode(png: bytes) -> str:
    cv2 = pytest.importorskip("cv2")  # only checked where OpenCV happens to be installed
    np = pytest.importorskip("numpy")
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    return cv2.QRCodeDetector().detectAndDecode(img)[0]


# ---- colours -----------------------------------------------------------------------------------


@pytest.mark.parametrize("raw, expected", [
    ("#1A2B3C", "#1a2b3c"), ("1a2b3c", "#1a2b3c"), ("#abc", "#aabbcc"), (" #FFF ", "#ffffff"),
])
def test_colours_are_read_in_any_of_the_usual_ways(raw, expected):
    assert parse_color(raw) == expected


@pytest.mark.parametrize(
    "raw", ["", None, "red", "#12", "#12345", "#1234567", "#ggg", "rgb(1,2,3)"]
)
def test_other_colour_values_are_refused(raw):
    with pytest.raises(ValueError, match="#RRGGBB"):
        parse_color(raw)


def test_contrast_ratios_match_the_web_standard():
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast_ratio("#777777", "#777777") == pytest.approx(1.0)
    assert contrast_ratio("#ffffff", "#000000") == contrast_ratio("#000000", "#ffffff")


@pytest.mark.parametrize("fg, bg", [
    ("#000000", "#ffffff"), ("#1b3a6b", "#fdf6e3"), ("#7a1f1f", "#fff4f4"), ("#000000", "#ffff00"),
])
def test_dark_on_light_with_good_contrast_is_accepted(fg, bg):
    assert contrast_ratio(fg, bg) >= MIN_CONTRAST
    check_colors(fg, bg)


@pytest.mark.parametrize("fg, bg", [
    ("#ffffff", "#000000"),  # light on dark: many scanners fail on inverted codes
    ("#888888", "#999999"),  # too little contrast
    ("#ff0000", "#00ff00"),  # loud but low in brightness difference
    ("#000000", "#000000"),
    ("#cccccc", "#ffffff"),
])
def test_light_on_dark_or_low_contrast_is_refused(fg, bg):
    with pytest.raises(ValueError, match="more contrast"):
        check_colors(fg, bg)


# ---- the logo ------------------------------------------------------------------------------------


def test_a_logo_becomes_a_small_png():
    out = process_logo(picture((1200, 800)))
    image = Image.open(io.BytesIO(out))
    assert image.format == "PNG" and max(image.size) == 256 and image.mode == "RGBA"
    assert image.size == (256, 171)  # the shape is kept


def test_small_logos_are_not_stretched():
    assert Image.open(io.BytesIO(process_logo(picture((40, 40))))).size == (40, 40)


@pytest.mark.parametrize("fmt", ["JPEG", "WEBP"])
def test_jpg_and_webp_logos_are_accepted(fmt):
    out = process_logo(picture((300, 300), (10, 120, 200, 255), fmt))
    assert Image.open(io.BytesIO(out)).format == "PNG"


@pytest.mark.parametrize("data", [
    b"", b"not a picture", b"GIF89a" + b"\x00" * 30, picture(fmt="PNG")[:60],
    b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
    b"\x00" * (MAX_LOGO_BYTES + 1),
])
def test_things_that_are_not_usable_pictures_are_refused(data):
    with pytest.raises(ValueError, match="PNG, JPG or WebP"):
        process_logo(data)


def test_a_gif_is_refused_even_though_it_is_a_picture():
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), "red").save(buf, format="GIF")
    with pytest.raises(ValueError, match="PNG, JPG or WebP"):
        process_logo(buf.getvalue())


# ---- drawing ---------------------------------------------------------------------------------


def test_the_default_png_is_the_same_size_as_the_old_plain_code():
    import qrcode

    old = io.BytesIO()
    qrcode.make(URL).save(old, format="PNG")  # how the site drew QR codes before styles existed
    image = Image.open(io.BytesIO(png_bytes(URL)))
    assert image.format == "PNG" and image.size == Image.open(io.BytesIO(old.getvalue())).size
    assert image.getpixel((0, 0)) == (255, 255, 255)  # the quiet zone is white


def test_the_colours_are_used():
    image = Image.open(io.BytesIO(png_bytes(URL, QrStyle("#123456", "#fff8e1"))))
    assert image.getpixel((0, 0)) == (0xFF, 0xF8, 0xE1)
    assert (0x12, 0x34, 0x56) in {p for p in image.getdata()}


def test_a_logo_covers_the_middle_and_only_the_middle():
    logo = process_logo(picture((200, 200), (200, 30, 30, 255)))
    styled = Image.open(io.BytesIO(png_bytes(URL, QrStyle(logo=logo)))).convert("RGB")
    centre = (styled.width // 2, styled.height // 2)
    assert styled.getpixel(centre) == (200, 30, 30)  # the logo's colour, in the middle
    assert styled.getpixel((5, 5)) == (255, 255, 255)  # the corner is untouched
    quarter = styled.width // 4
    assert styled.getpixel((quarter, quarter)) in {(0, 0, 0), (255, 255, 255)}  # code, not logo


def test_the_style_version_changes_with_the_look():
    base = QrStyle().version
    assert QrStyle("#111111").version != base and QrStyle(bg="#fefefe").version != base
    assert QrStyle(logo=b"abc").version != base and QrStyle().version == base


def test_default_style_is_recognised():
    assert QrStyle().is_default and not QrStyle("#111111").is_default
    assert not QrStyle(logo=b"x").is_default


def test_the_svg_is_well_formed_and_uses_the_colours():
    svg = svg_text(URL, QrStyle("#123456", "#fff8e1"))
    root = ET.fromstring(svg)
    assert root.tag == "{http://www.w3.org/2000/svg}svg" and root.get("viewBox").startswith("0 0 ")
    assert root.find("s:rect", NS).get("fill") == "#fff8e1"
    assert root.find("s:path", NS).get("fill") == "#123456"
    assert root.find("s:image", NS) is None
    assert "<script" not in svg and "javascript" not in svg


def test_the_svg_logo_is_embedded_and_nothing_else_is_linked():
    svg = svg_text(URL, QrStyle(logo=process_logo(picture())))
    root = ET.fromstring(svg)
    image = root.find("s:image", NS)
    assert image.get("href").startswith("data:image/png;base64,")
    assert "http://" not in svg.replace("http://www.w3.org", "")


def test_the_svg_and_png_are_the_same_picture():
    cells = len(Image.open(io.BytesIO(png_bytes(URL))).convert("1").getdata())
    root = ET.fromstring(svg_text(URL))
    side = int(root.get("viewBox").split()[2])
    assert side * side * 100 == cells  # 10 x 10 pixels per square in the PNG


@pytest.mark.parametrize("style", [
    QrStyle(), QrStyle("#123456", "#fff8e1"), QrStyle("#1b3a6b", "#fdf6e3"),
])
def test_styled_codes_still_scan(style):
    assert decode(png_bytes(URL, style)) == URL


def test_a_code_with_a_logo_still_scans():
    logo = process_logo(picture((300, 200)))
    assert decode(png_bytes(URL, QrStyle(logo=logo))) == URL
    assert decode(png_bytes(URL, QrStyle("#1b3a6b", "#fdf6e3", logo))) == URL


def test_a_long_address_with_a_logo_still_scans():
    long_url = URL + "?utm_source=instagram&utm_medium=social&utm_campaign=summer-sale-2026"
    assert decode(png_bytes(long_url, QrStyle(logo=process_logo(picture())))) == long_url


# ---- the routes ------------------------------------------------------------------------------


def test_the_svg_route_serves_a_safe_image(alice, app):
    make(alice)
    r = alice.get(f"/dashboard/links/{row(app)['id']}/qr.svg")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "content-disposition" not in r.headers
    ET.fromstring(r.text)


def test_the_svg_can_be_downloaded(alice, app):
    make(alice, "mine")
    r = alice.get(f"/dashboard/links/{row(app, 'mine')['id']}/qr.svg?download=1")
    assert r.headers["content-disposition"] == 'attachment; filename="mine-qr.svg"'


def test_qr_files_belong_to_their_owner(alice, make_client, app):
    make(alice)
    link_id = row(app)["id"]
    bob = make_client()
    bob.post("/register", data={"username": "bob", "email": "bob@example.com",
                                "password": "password123"})
    for path in ("qr.png", "qr.svg"):
        assert bob.get(f"/dashboard/links/{link_id}/{path}").status_code == 404
    assert bob.post(f"/dashboard/links/{link_id}/qr-style",
                    data={"qr_fg": "#000000", "qr_bg": "#ffffff"}).status_code == 404


def test_colours_are_saved_and_used_by_both_formats(alice, app):
    make(alice)
    link_id = row(app)["id"]
    plain_png = alice.get(f"/dashboard/links/{link_id}/qr.png").content
    save(alice, link_id, qr_fg="#1b3a6b", qr_bg="#fdf6e3")
    assert (row(app)["fg"], row(app)["bg"]) == ("#1b3a6b", "#fdf6e3")
    styled = alice.get(f"/dashboard/links/{link_id}/qr.png").content
    assert styled != plain_png
    assert Image.open(io.BytesIO(styled)).getpixel((0, 0)) == (0xFD, 0xF6, 0xE3)
    assert 'fill="#1b3a6b"' in alice.get(f"/dashboard/links/{link_id}/qr.svg").text
    assert "QR code style saved." in alice.get("/dashboard").text


def test_the_default_colours_are_stored_as_nothing(alice, app):
    make(alice)
    save(alice, row(app)["id"], qr_fg="#1b3a6b")
    save(alice, row(app)["id"], qr_fg=DEFAULT_FG, qr_bg=DEFAULT_BG)
    assert (row(app)["fg"], row(app)["bg"]) == (None, None)


def test_a_logo_is_stored_resized_and_drawn(alice, app):
    make(alice)
    link_id = row(app)["id"]
    save(alice, link_id, logo=picture((900, 900), (200, 30, 30, 255)))
    stored = row(app)["logo"]
    assert Image.open(io.BytesIO(stored)).size == (256, 256)
    image = Image.open(io.BytesIO(alice.get(f"/dashboard/links/{link_id}/qr.png").content))
    assert image.convert("RGB").getpixel((image.width // 2, image.height // 2)) == (200, 30, 30)
    assert "data:image/png;base64," in alice.get(f"/dashboard/links/{link_id}/qr.svg").text


def test_saving_colours_again_keeps_the_logo_and_remove_deletes_it(alice, app):
    make(alice)
    link_id = row(app)["id"]
    save(alice, link_id, logo=picture())
    save(alice, link_id, qr_fg="#1b3a6b")  # no new file: the logo stays
    assert row(app)["logo"] and row(app)["fg"] == "#1b3a6b"
    save(alice, link_id, qr_fg="#1b3a6b", remove_logo="1")
    assert row(app)["logo"] is None and row(app)["fg"] == "#1b3a6b"


def test_a_new_logo_replaces_the_old_one(alice, app):
    make(alice)
    link_id = row(app)["id"]
    save(alice, link_id, logo=picture((100, 100), (1, 2, 3, 255)))
    first = row(app)["logo"]
    save(alice, link_id, logo=picture((100, 100), (9, 8, 7, 255)))
    assert row(app)["logo"] != first


def test_reset_goes_back_to_the_plain_code(alice, app):
    make(alice)
    link_id = row(app)["id"]
    save(alice, link_id, qr_fg="#1b3a6b", logo=picture())
    r = alice.post(f"/dashboard/links/{link_id}/qr-style", data={"reset": "1"})
    assert r.status_code == 303 and r.headers["location"].endswith("/edit#qr")
    assert row(app) == {"id": link_id, "fg": None, "bg": None, "logo": None}
    assert "back to the plain style" in alice.get("/dashboard").text


@pytest.mark.parametrize("fields, message", [
    ({"qr_fg": "#ffffff", "qr_bg": "#000000"}, "more contrast"),
    ({"qr_fg": "#999999", "qr_bg": "#aaaaaa"}, "more contrast"),
    ({"qr_fg": "blue"}, "#RRGGBB"),
])
def test_bad_colours_change_nothing_and_say_why(alice, app, fields, message):
    make(alice)
    link_id = row(app)["id"]
    save(alice, link_id, **fields)
    assert row(app) == {"id": link_id, "fg": None, "bg": None, "logo": None}
    assert message in alice.get("/dashboard").text


def test_a_bad_logo_changes_nothing_and_says_why(alice, app):
    make(alice)
    link_id = row(app)["id"]
    save(alice, link_id, qr_fg="#1b3a6b", logo=b"not a picture")
    assert row(app)["logo"] is None and row(app)["fg"] is None  # nothing was half-saved
    assert "PNG, JPG or WebP" in alice.get("/dashboard").text


def test_the_zip_uses_each_links_own_style_and_can_be_svg(alice, app):
    make(alice, "one")
    make(alice, "two")
    save(alice, row(app, "one")["id"], qr_fg="#1b3a6b", qr_bg="#fdf6e3")
    z = zipfile.ZipFile(io.BytesIO(alice.get("/dashboard/links/qr.zip").content))
    assert sorted(z.namelist()) == ["one.png", "two.png"]
    assert Image.open(io.BytesIO(z.read("one.png"))).getpixel((0, 0)) == (0xFD, 0xF6, 0xE3)
    assert Image.open(io.BytesIO(z.read("two.png"))).getpixel((0, 0)) == (255, 255, 255)
    svg = zipfile.ZipFile(io.BytesIO(alice.get("/dashboard/links/qr.zip?format=svg").content))
    assert sorted(svg.namelist()) == ["one.svg", "two.svg"]
    assert 'fill="#1b3a6b"' in svg.read("one.svg").decode()
    other = zipfile.ZipFile(io.BytesIO(alice.get("/dashboard/links/qr.zip?format=exe").content))
    assert sorted(other.namelist()) == ["one.png", "two.png"]  # anything else means PNG


def test_the_zip_loads_logos_in_one_go(alice, app):
    make(alice, "one")
    make(alice, "two")
    for slug in ("one", "two"):
        save(alice, row(app, slug)["id"], logo=picture())
    z = zipfile.ZipFile(io.BytesIO(alice.get("/dashboard/links/qr.zip").content))
    assert all(b"PNG" in z.read(n)[:8] for n in z.namelist())


def test_logos_are_not_loaded_with_every_link():
    assert inspect(Link).column_attrs.qr_logo.deferred is True


# ---- the screens -----------------------------------------------------------------------------


def test_the_edit_page_has_the_qr_panel(alice, app):
    make(alice)
    link_id = row(app)["id"]
    page = alice.get(f"/dashboard/links/{link_id}/edit").text
    assert 'id="qr"' in page and 'type="color" name="qr_fg" value="#000000"' in page
    assert 'type="color" name="qr_bg" value="#ffffff"' in page and 'name="logo"' in page
    assert 'enctype="multipart/form-data"' in page and "remove_logo" not in page
    assert f"/dashboard/links/{link_id}/qr.png?v=" in page
    assert f"/dashboard/links/{link_id}/qr.svg?download=1" in page
    save(alice, link_id, qr_fg="#1b3a6b", logo=picture())
    page = alice.get(f"/dashboard/links/{link_id}/edit").text
    assert 'value="#1b3a6b"' in page and 'name="remove_logo"' in page


def test_the_preview_picture_changes_address_when_the_style_changes(alice, app):
    make(alice)
    link_id = row(app)["id"]
    before = re.search(r"qr\.png\?v=(\w+)", alice.get(f"/dashboard/links/{link_id}/edit").text)
    save(alice, link_id, qr_fg="#1b3a6b")
    after = re.search(r"qr\.png\?v=(\w+)", alice.get(f"/dashboard/links/{link_id}/edit").text)
    assert before.group(1) != after.group(1)


def test_the_analytics_page_offers_png_svg_and_the_style_link(alice, app):
    make(alice)
    link_id = row(app)["id"]
    page = alice.get(f"/dashboard/links/{link_id}").text
    assert "Download PNG" in page and "Download SVG" in page and "Change style" in page
    assert f"/dashboard/links/{link_id}/qr.svg?download=1" in page
    assert f"/dashboard/links/{link_id}/edit#qr" in page


def test_the_share_popup_has_an_svg_download(alice):
    make(alice)
    page = alice.get("/dashboard").text
    assert 'id="share-qr-svg"' in page and "Download QR as SVG" in page
    js = alice.get("/static/share.js").text
    assert "/qr.svg?download=1" in js


def test_the_dashboard_qr_button_is_unchanged(alice, app):
    make(alice)
    assert f'href="/dashboard/links/{row(app)["id"]}/qr.png?download=1"' in alice.get(
        "/dashboard").text


# ---- the paid-plan gate ----------------------------------------------------------------------


def test_a_locked_qr_style_cannot_be_changed_but_can_be_reset(alice, app, monkeypatch):
    make(alice)
    link_id = row(app)["id"]
    save(alice, link_id, qr_fg="#1b3a6b", logo=picture())
    monkeypatch.setattr(features, "PAID", frozenset({"qr_style"}))
    page = alice.get(f"/dashboard/links/{link_id}/edit").text
    assert re.search(r'name="qr_fg"[^>]*disabled', page) and "paid plan" in page
    assert "Save QR style" not in page and "Back to the plain code" in page
    save(alice, link_id, qr_fg="#7a1f1f")  # posting by hand
    assert row(app)["fg"] == "#1b3a6b"
    assert "paid plan" in alice.get("/dashboard").text
    assert alice.get(f"/dashboard/links/{link_id}/qr.png").status_code == 200  # still renders
    alice.post(f"/dashboard/links/{link_id}/qr-style", data={"reset": "1"})
    assert row(app)["fg"] is None and row(app)["logo"] is None


def test_a_locked_account_can_still_save_the_plain_style(alice, app, monkeypatch):
    make(alice)
    monkeypatch.setattr(features, "PAID", frozenset({"qr_style"}))
    r = save(alice, row(app)["id"])
    assert r.status_code == 303 and "QR code style saved." in alice.get("/dashboard").text


@pytest.mark.parametrize("lang, word", [("hi", "QR शैली सहेजें"), ("gu", "QR શૈલી સાચવો")])
def test_the_qr_screens_render_in_every_language(alice, app, lang, word):
    make(alice)
    alice.post("/language", data={"lang": lang, "next": "/"})
    assert word in alice.get(f"/dashboard/links/{row(app)['id']}/edit").text


def test_migration_adds_the_columns():
    text = open("alembic/versions/0012_preview_qr_style.py", encoding="utf-8").read()
    for name in ("preview", "preview_message", "qr_fg", "qr_bg", "qr_logo"):
        assert f"'{name}'" in text and hasattr(Link, name)
    assert "down_revision = '0011'" in text
