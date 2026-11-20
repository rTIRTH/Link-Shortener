"""The "back" links at the top of the inner pages are buttons, not bare text links."""

import re

import pytest

from app.models import Link, utcnow


def make(client, slug):
    client.post("/dashboard/links", data={"original_url": "https://example.com/" + slug,
                                          "slug": slug})


@pytest.fixture()
def pages(alice, app):
    make(alice, "one")
    make(alice, "two")
    with app.state.session_factory() as db:
        ids = [link.id for link in db.query(Link).order_by(Link.id)]
    day = utcnow().date().isoformat()
    return {
        "analytics": f"/dashboard/links/{ids[0]}",
        "edit": f"/dashboard/links/{ids[0]}/edit",
        "compare": f"/dashboard/links/compare?ids={ids[0]}&ids={ids[1]}",
        "import": "/dashboard/links/import",
        "day": f"/dashboard/links/{ids[0]}/day/{day}",
    }, ids[0]


def backbar(page: str) -> str:
    start = page.index('<p class="backbar">')
    return page[start:page.index("</p>", start)]


def links_in(block: str):
    return re.findall(r'<a class="([^"]*)" href="([^"]*)">(.*?)</a>', block, re.S)


@pytest.mark.parametrize("name", ["analytics", "compare", "import"])
def test_the_all_links_pages_have_a_back_button(alice, pages, name):
    paths, _id = pages
    found = links_in(backbar(alice.get(paths[name]).text))
    assert found == [("btn small ghost", "/dashboard", "← All links")]


def test_the_edit_page_has_two_buttons(alice, pages):
    paths, link_id = pages
    found = links_in(backbar(alice.get(paths["edit"]).text))
    assert [(c, h) for c, h, _ in found] == [
        ("btn small ghost", "/dashboard"),
        ("btn small ghost has-icon", f"/dashboard/links/{link_id}"),
    ]
    assert found[0][2] == "← All links"
    assert "<svg" in found[1][2] and "<span>Analytics</span>" in found[1][2]


def test_the_day_page_goes_back_to_the_analytics_page_with_a_button(alice, pages):
    paths, link_id = pages
    found = links_in(backbar(alice.get(paths["day"]).text))
    assert found == [("btn small ghost", f"/dashboard/links/{link_id}", "← Back to link analytics")]


def test_no_page_still_has_a_bare_text_back_link(alice, pages):
    paths, _id = pages
    for page in (alice.get(p).text for p in paths.values()):
        assert not re.search(r'<p><a href="/dashboard[^"]*">← ', page)


def test_the_buttons_sit_in_a_row_with_a_gap():
    css = open("app/static/style.css", encoding="utf-8").read()
    assert re.search(r"\.backbar\s*\{[^}]*display:\s*flex[^}]*gap:\s*10px", css)


@pytest.mark.parametrize("lang, back", [("hi", "सभी लिंक"), ("gu", "બધી લિંક")])
def test_the_buttons_keep_their_translations(alice, pages, lang, back):
    paths, _id = pages
    alice.post("/language", data={"lang": lang, "next": "/"})
    assert back in backbar(alice.get(paths["analytics"]).text)
    assert "Analytics" not in backbar(alice.get(paths["edit"]).text)
