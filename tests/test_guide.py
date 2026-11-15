"""The Features / Guide page."""

import re
from html import unescape

import pytest

from app.models import Link

SECTIONS = ["create", "schedule", "password", "limit", "tags", "archive", "edit", "analytics",
            "share", "data", "safety"]


def cards(page):
    return re.findall(r'<section class="guide-card" id="(\w+)">(.*?)</section>', page, re.S)


def test_the_guide_is_open_to_everyone(make_client, alice):
    assert make_client().get("/guide").status_code == 200  # a visitor with no account
    assert alice.get("/guide").status_code == 200


def test_every_feature_has_a_card_with_steps_and_a_jump_link(client):
    page = client.get("/guide").text
    found = cards(page)
    assert [i for i, _ in found] == SECTIONS
    for section, body in found:
        steps = re.findall(r"<li>(.+?)</li>", body, re.S)
        assert 3 <= len(steps) <= 4, section
        assert re.search(r"<h2>[^<]+</h2>\s*<p class=\"muted\">[^<]+</p>", body), section
    nav = re.findall(r'<a class="chip" href="#(\w+)">', page)
    assert nav == SECTIONS  # one jump link per card, in the same order


def test_the_guide_link_is_in_the_top_bar_for_everyone(make_client, alice):
    for page in (make_client().get("/").text, alice.get("/dashboard").text):
        assert '<a class="navlink" href="/guide">Guide</a>' in page


def test_the_call_to_action_depends_on_who_is_looking(make_client, alice):
    anon = make_client().get("/guide").text
    assert 'href="/register"' in anon and "Create a free account" in anon
    assert "Go to my links" not in anon
    me = alice.get("/guide").text
    assert 'href="/dashboard">Go to my links' in me and "Create a free account" not in me


def test_nobody_can_take_guide_as_a_username(client):
    r = client.post("/register", data={"username": "guide", "email": "g@example.com",
                                       "password": "password123"})
    assert "reserved" in r.text


def test_the_guide_names_buttons_that_really_exist(alice, app):
    """If a button is renamed, the guide has to be updated too."""
    alice.post("/dashboard/links", data={
        "original_url": "https://example.com/a", "slug": "one", "tags": "work"})
    alice.post("/dashboard/links", data={"original_url": "https://example.com/b", "slug": "two"})
    with app.state.session_factory() as db:
        two = db.query(Link).filter_by(slug="two").one().id
        one = db.query(Link).filter_by(slug="one").one().id
    alice.post("/dashboard/links/archive", data={"ids": [two], "action": "archive"})
    pages = [
        alice.get("/dashboard").text, alice.get("/dashboard?tag=work").text,
        alice.get("/dashboard?view=archived").text, alice.get(f"/dashboard/links/{one}/edit").text,
        alice.get(f"/dashboard/links/{one}").text, alice.get("/dashboard/links/import").text,
    ]
    screens = unescape(" ".join(pages))
    guide = unescape(alice.get("/guide").text)
    named = ["Long URL", "Custom alias", "Shorten", "More options", "Edit", "Set a password",
             "No password", "Advanced", "Click limit", "Archive", "Archived", "Restore",
             "Deactivate link", "Compare this tag", "Analytics", "Audience", "Share",
             "Download QR", "Download QR codes", "Export CSV",
             "Import many links from a CSV file"]
    for label in named:
        assert label in screens, f"the guide mentions '{label}' but no screen has it"
        assert label in guide, f"'{label}' is not used in the guide any more"


@pytest.mark.parametrize("lang, title, step_word", [
    ("hi", "गाइड", "\"छोटा करें\""), ("gu", "માર્ગદર્શિકા", "\"ટૂંકું કરો\""),
])
def test_the_guide_reads_in_every_language(client, lang, title, step_word):
    client.cookies.set("lang", lang)
    page = unescape(client.get("/guide").text)
    assert title in page and step_word in page
    for english in ("Create a short link", "Schedule a link", "Everything this site can do",
                    "Press Shorten"):
        assert english not in page
    assert len(cards(page)) == 11


def test_the_guide_does_not_need_a_login_cookie_to_switch_language(client):
    client.cookies.set("lang", "hi")
    assert 'lang="hi"' in client.get("/guide").text
