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


@pytest.mark.parametrize("lang", ["hi", "gu"])
def test_edit_button_is_translated(alice, app, lang):
    make(alice)
    alice.post("/language", data={"lang": lang, "next": "/"})
    page = page_for(alice, app)
    assert f"<span>{translate(lang, 'Edit link')}</span>" in page


def test_toolbar_icons_are_unchanged_by_the_new_icon_argument(alice):
    make(alice)
    for icon in svgs(alice.get("/dashboard").text):
        assert 'class="ico"' in icon  # no stray extra class on the existing icons
