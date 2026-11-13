"""The link's analytics page header: the Edit link button icon and the copy button."""

import re
from pathlib import Path

import pytest

from app.i18n import translate
from app.models import Link

APP = Path(__file__).resolve().parent.parent / "app"
URL = "https://example.com/page"


def make(client, slug="lnk", url=URL):
    return client.post("/dashboard/links", data={"original_url": url, "slug": slug})


def page_for(client, app):
    with app.state.session_factory() as db:
        link_id = db.query(Link).one().id
    return client.get(f"/dashboard/links/{link_id}").text


def svgs(html: str) -> list[str]:
    return re.findall(r'<svg class="ico[^"]*".*?</svg>', html, re.S)


def test_edit_link_button_has_the_same_icon_as_the_toolbar_edit_button(alice, app):
    make(alice)
    dashboard = alice.get("/dashboard").text
    toolbar_edit = re.search(r'id="edit-selected".*?</button>', dashboard, re.S)
    page = page_for(alice, app)
    button = re.search(r'<a class="btn small has-icon" href="/dashboard/links/\d+/edit">.*?</a>',
                       page, re.S).group(0)
    icon = svgs(button)
    assert len(icon) == 1 and button.index("<svg") < button.index("<span>Edit link</span>")
    assert icon[0] == svgs(toolbar_edit.group(0))[0]  # exactly the same drawing


def test_copy_button_sits_right_after_the_redirects_to_line(alice, app):
    make(alice)
    page = page_for(alice, app)
    line = re.search(r'<p class="dest-full">.*?</p>', page, re.S).group(0)
    assert line.index("Redirects to") < line.index(f'href="{URL}"') < line.index("copy-btn")
    button = re.search(r'<button[^>]*copy-btn[^>]*>.*?</button>', line, re.S).group(0)
    assert f'data-copy="{URL}"' in button and 'type="button"' in button
    assert 'aria-label="Copy destination link"' in button
    assert 'title="Copy destination link"' in button
    assert 'aria-live="polite"' in line  # "Copied!" is announced


def test_copy_icon_is_two_squares_with_the_plain_link_and_no_pencil(alice, app):
    make(alice)
    page = page_for(alice, app)
    button = re.search(r'<button[^>]*copy-btn[^>]*>.*?</button>', page, re.S).group(0)
    copy_icon, done_icon = svgs(button)
    assert 'class="ico ico-copy"' in copy_icon and 'class="ico ico-done"' in done_icon
    assert 'rx="3.5"' in copy_icon  # the front square, with rounded corners
    assert "M8 8V5.5" in copy_icon  # the back square peeking out behind it
    assert "M7.7 13.2" in copy_icon and "M10.3 13.2" in copy_icon  # the two link halves
    edit_button = re.search(r'<a class="btn small has-icon".*?</a>', page, re.S).group(0)
    edit_icon = svgs(edit_button)[0]
    assert "M11.2 18.2" in edit_icon and "M11.2 18.2" not in copy_icon  # the pencil stays out
    assert 'aria-hidden="true"' in copy_icon and 'aria-hidden="true"' in done_icon  # decorative


def test_the_url_is_copied_exactly_even_with_special_characters(alice, app):
    make(alice, url="https://example.com/search?q=a&lang=hi&x=1")
    page = page_for(alice, app)
    assert 'data-copy="https://example.com/search?q=a&amp;lang=hi&amp;x=1"' in page  # escaped HTML
    assert "<script>" not in re.search(r'<button[^>]*copy-btn[^>]*>', page).group(0)


def test_script_is_loaded_and_served(alice, app, client):
    make(alice)
    page = page_for(alice, app)
    assert re.search(r'<script src="/static/copy\.js\?v=[^"]+" defer></script>', page)
    r = client.get("/static/copy.js")
    assert r.status_code == 200 and "javascript" in r.headers["content-type"]
    js = r.text
    assert "navigator.clipboard.writeText" in js and "execCommand('copy')" in js  # with a fallback
    assert "data-copy" in js and "share_copied" in js and "share_copy_failed" in js


def test_copy_script_is_not_loaded_on_pages_that_do_not_need_it(alice, app):
    make(alice)
    assert "copy.js" not in alice.get("/dashboard").text


@pytest.mark.parametrize("lang", ["hi", "gu"])
def test_copy_button_and_edit_button_are_translated(alice, app, lang):
    make(alice)
    alice.post("/language", data={"lang": lang, "next": "/"})
    page = page_for(alice, app)
    label = translate(lang, "Copy destination link")
    assert f'aria-label="{label}"' in page and label != "Copy destination link"
    assert "Copy destination link" not in page
    assert f"<span>{translate(lang, 'Edit link')}</span>" in page


def test_toolbar_icons_are_unchanged_by_the_new_icon_argument(alice):
    make(alice)
    for icon in svgs(alice.get("/dashboard").text):
        assert 'class="ico"' in icon  # no stray extra class on the existing icons
