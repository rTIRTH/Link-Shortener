"""Own profile photo: upload, checking, privacy, removal."""
import io
import os

import pytest
from PIL import Image

from app.models import ProfilePhoto, User
from tests.conftest import register

PW = "password123"


def picture(fmt="JPEG", size=(400, 300), mode="RGB", color="red", **save_args):
    out = io.BytesIO()
    Image.new(mode, size, color).save(out, fmt, **save_args)
    return out.getvalue()


def upload(client, data, name="photo.jpg", content_type="image/jpeg"):
    return client.post("/account/photo", files={"photo": (name, data, content_type)})


def stored(app, user_id=1):
    with app.state.session_factory() as db:
        row = db.get(ProfilePhoto, user_id)
        return row.data if row else None


def user_row(app):
    with app.state.session_factory() as db:
        return db.query(User).filter_by(username="alice").one()


# ---------- uploading and serving ----------

def test_upload_is_stored_as_a_clean_256_square_jpeg(alice, app):
    r = upload(alice, picture())
    assert r.status_code == 200 and r.json() == {"ok": True}
    image = Image.open(io.BytesIO(stored(app)))
    assert image.format == "JPEG" and image.size == (256, 256)
    assert user_row(app).photo_updated_at is not None


def test_the_photo_is_served_privately_to_its_owner(alice):
    upload(alice, picture())
    r = alice.get("/account/photo")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert "private" in r.headers["cache-control"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert Image.open(io.BytesIO(r.content)).size == (256, 256)


@pytest.mark.parametrize("fmt,mode", [("PNG", "RGB"), ("WEBP", "RGB"), ("PNG", "RGBA")])
def test_png_and_webp_are_accepted(alice, app, fmt, mode):
    assert upload(alice, picture(fmt, mode=mode), "p." + fmt.lower()).status_code == 200
    assert Image.open(io.BytesIO(stored(app))).mode == "RGB"


def test_see_through_pictures_get_a_white_background(alice, app):
    upload(alice, picture("PNG", mode="RGBA", color=(0, 0, 0, 0)), "p.png", "image/png")
    assert Image.open(io.BytesIO(stored(app))).getpixel((5, 5)) == (255, 255, 255)


def test_hidden_location_data_is_removed(alice, app):
    exif = Image.Exif()
    exif[0x010F] = "SecretPhoneMaker"          # camera make; GPS data is stripped the same way
    exif[0x8825] = {1: "N", 2: (12.0, 34.0, 56.0)}
    original = picture(exif=exif.tobytes())
    assert b"SecretPhoneMaker" in original
    upload(alice, original)
    saved = stored(app)
    assert b"SecretPhoneMaker" not in saved and len(Image.open(io.BytesIO(saved)).getexif()) == 0


def test_non_square_pictures_are_centre_cropped(alice, app):
    wide = Image.new("RGB", (600, 200), "blue")
    wide.paste(Image.new("RGB", (200, 200), "red"), (200, 0))   # red square in the middle
    out = io.BytesIO()
    wide.save(out, "PNG")
    upload(alice, out.getvalue(), "w.png", "image/png")
    saved = Image.open(io.BytesIO(stored(app)))
    assert saved.getpixel((128, 128))[0] > 200 and saved.getpixel((128, 128))[2] < 60


def test_a_new_photo_replaces_the_old_one(alice, app):
    upload(alice, picture(color="red"))
    first = stored(app)
    version_1 = alice.get("/dashboard").text.split("/account/photo?v=")[1][:13]
    upload(alice, picture(color="blue"))
    assert stored(app) != first
    assert alice.get("/dashboard").text.split("/account/photo?v=")[1][:13] != version_1


# ---------- things that must be refused ----------

@pytest.mark.parametrize("data,name", [
    (b"just some text, not a picture", "note.jpg"),
    (b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "x.svg"),
    (b"GIF89a" + b"\x00" * 40, "x.gif"),
    (b"", "empty.jpg"),
    (picture()[:200], "cut-off.jpg"),                         # a truncated JPEG
])
def test_files_that_are_not_real_photos_are_refused(alice, app, data, name):
    r = upload(alice, data, name)
    assert r.status_code == 400 and "not a valid photo" in r.json()["error"]
    assert stored(app) is None and user_row(app).photo_updated_at is None


def test_a_real_gif_is_not_an_allowed_format(alice, app):
    assert upload(alice, picture("GIF", mode="P"), "a.gif", "image/gif").status_code == 400
    assert stored(app) is None


def test_files_over_two_megabytes_are_refused(alice, app):
    r = upload(alice, b"\xff\xd8\xff" + os.urandom(2 * 1024 * 1024 + 10))
    assert r.status_code == 400 and "too large" in r.json()["error"]
    assert stored(app) is None


def test_decompression_bombs_are_refused(alice, app):
    bomb = picture("PNG", size=(6000, 6000), mode="1", color=0)   # tiny file, 36 million pixels
    assert len(bomb) < 100_000
    r = upload(alice, bomb, "big.png", "image/png")
    assert r.status_code == 400 and "dimensions are too large" in r.json()["error"]
    assert stored(app) is None


def test_uploads_need_a_login(client):
    assert upload(client, picture()).status_code == 303
    assert client.get("/account/photo").status_code == 303


def test_ten_uploads_an_hour_is_the_limit(alice):
    codes = [upload(alice, picture()).status_code for _ in range(11)]
    assert codes[:10] == [200] * 10 and codes[10] == 429


def test_a_failed_upload_leaves_the_old_photo_alone(alice, app):
    upload(alice, picture(color="red"))
    before = stored(app)
    upload(alice, b"not a picture")
    assert stored(app) == before


# ---------- privacy ----------

def test_nobody_can_fetch_someone_elses_photo(alice, make_client):
    upload(alice, picture())
    bob = make_client()
    register(bob, "bob")
    assert bob.get("/account/photo").status_code == 404        # Bob only ever gets his own
    assert bob.get("/account/photo?user=1").status_code == 404
    assert "/account/photo" not in bob.get("/dashboard").text


# ---------- using and removing it ----------

def test_pages_show_the_photo_instead_of_the_animal(alice):
    assert "/static/avatars/" in alice.get("/dashboard").text
    upload(alice, picture())
    for url in ("/dashboard", "/account"):
        page = alice.get(url).text
        assert "/account/photo?v=" in page
    assert '<img class="avatar" src="/static/avatars/' not in alice.get("/dashboard").text


def test_removing_the_photo_brings_the_animal_back(alice, app):
    upload(alice, picture())
    r = alice.post("/account/photo/remove")
    assert r.status_code == 303 and r.headers["location"] == "/account"
    assert stored(app) is None and user_row(app).photo_updated_at is None
    assert "Profile photo removed." in alice.get("/account").text   # shown once, on the next page
    assert alice.get("/account/photo").status_code == 404
    assert "/static/avatars/" in alice.get("/dashboard").text


def test_picking_an_animal_replaces_the_photo(alice, app):
    upload(alice, picture())
    alice.post("/account/avatar", data={"avatar": "panda"})
    assert stored(app) is None and "/static/avatars/panda.svg" in alice.get("/dashboard").text


def test_deleting_the_account_deletes_the_photo(alice, app):
    upload(alice, picture())
    alice.post("/account/delete", data={"confirm": "alice", "password": PW})
    with app.state.session_factory() as db:
        assert db.query(ProfilePhoto).count() == 0


# ---------- the page ----------

def test_account_page_has_the_pencil_and_the_editor(alice):
    page = alice.get("/account").text
    for needle in ('id="photo-open"', 'id="photo-dialog"', 'id="pd-canvas"', 'id="pd-zoom"',
                   'id="pd-angle"', 'id="pd-save"', 'id="pd-camera"', 'id="pd-upload"'):
        assert needle in page, needle
    assert "/static/photo-editor.js?v=" in page
    assert "Remove photo" not in page                          # nothing to remove yet
    upload(alice, picture())
    assert "Remove photo" in alice.get("/account").text
    assert "photo-editor.js" not in alice.get("/dashboard").text   # only loaded where needed


def test_the_editor_script_is_served(client):
    r = client.get("/static/photo-editor.js")
    assert r.status_code == 200 and "javascript" in r.headers["content-type"]


@pytest.mark.parametrize("lang,sample", [("hi", "गैलरी से अपलोड करें"), ("gu", "ગૅલેરીમાંથી અપલોડ કરો")])
def test_editor_is_translated(alice, lang, sample):
    alice.post("/language", data={"lang": lang, "next": "/"})
    assert sample in alice.get("/account").text


def test_upload_errors_are_translated(alice):
    alice.post("/language", data={"lang": "hi", "next": "/"})
    r = upload(alice, b"not a picture")
    assert "सही फ़ोटो नहीं है" in r.json()["error"]


def test_the_browser_gets_its_photo_messages(alice):
    import json
    import re

    alice.post("/language", data={"lang": "gu", "next": "/"})
    blob = re.search(r'id="i18n-data">(.*?)</script>', alice.get("/account").text, re.S).group(1)
    ui = json.loads(blob)["ui"]
    assert ui["photo_saving"] == "સાચવી રહ્યા છીએ…" and ui["photo_choose"]
