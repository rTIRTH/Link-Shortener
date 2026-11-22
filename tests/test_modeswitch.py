"""The light / system default / dark switch in the top bar."""

import re
from pathlib import Path

import pytest

from app import features
from app.models import User
from app.profile import THEMES
from app.templating import templates

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
CSS = (STATIC / "style.css").read_text(encoding="utf-8")
PW = "password123"


def user_of(app, name="alice") -> User:
    with app.state.session_factory() as db:
        return db.query(User).filter_by(username=name).one()


def switch(page: str) -> str:
    start = page.index('<form class="modeswitch"')
    return page[start:page.index("</form>", start)]


def buttons(page: str):
    return re.findall(r'<button type="submit" name="theme" value="(\w+)"([^>]*)>', switch(page))


# ---- the switch on every page --------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/", "/login", "/guide", "/register"])
def test_visitors_see_the_switch_in_the_top_bar(make_client, path):
    page = make_client().get(path).text
    assert [value for value, _ in buttons(page)] == ["light", "system", "dark"]
    assert 'role="radiogroup"' in switch(page) and 'action="/mode"' in switch(page)


def test_signed_in_pages_have_it_too(alice):
    for path in ("/dashboard", "/account", "/guide"):
        assert len(buttons(alice.get(path).text)) == 3, path


def test_the_current_mode_is_the_marked_one(alice):
    for mode in THEMES:
        alice.post("/mode", data={"theme": mode})
        found = {v: a for v, a in buttons(alice.get("/dashboard").text)}
        assert 'aria-checked="true"' in found[mode] and 'class="on"' in found[mode]
        assert all('aria-checked="false"' in a for v, a in found.items() if v != mode)


def test_each_button_has_an_icon_a_name_and_a_tooltip(make_client):
    box = switch(make_client().get("/").text)
    names = re.findall(r'aria-label="([^"]+)" title="([^"]+)"', box)
    assert names == [("Light", "Light"), ("System default", "System default"), ("Dark", "Dark")]
    assert box.count("<svg") == 3 and box.count('role="radio"') == 3
    assert 'aria-label="Colour mode"' in box
    icons = re.findall(r"<svg.*?</svg>", box, re.S)
    assert len(set(icons)) == 3 and "<circle" in icons[0] and "<rect" in icons[1]  # sun, monitor


def test_the_switch_sits_before_the_language_button_and_the_avatar(alice):
    page = alice.get("/dashboard").text
    assert page.index('class="modeswitch"') < page.index('id="langmenu"') < page.index(
        'id="usermenu"')
    assert page.index('class="brand"') < page.index('class="modeswitch"')


def test_the_rest_of_the_top_bar_is_unchanged(make_client):
    page = make_client().get("/").text
    bar = page[page.index("<header"):page.index("</header>")]
    assert 'class="brand"' in bar and 'href="/guide"' in bar and 'id="langmenu"' in bar
    assert 'href="/login"' in bar and 'href="/register"' in bar


def test_it_works_in_every_language(make_client):
    visitor = make_client()
    for lang, label in (("hi", "रंग मोड"), ("gu", "રંગ મોડ")):
        visitor.cookies.set("lang", lang)
        box = switch(visitor.get("/").text)
        assert f'aria-label="{label}"' in box
        assert "Light" not in box and "Dark" not in box and "System default" not in box


def test_the_switch_is_not_a_paid_feature(alice, monkeypatch):
    monkeypatch.setattr(features, "PAID", frozenset(features.FEATURES))  # lock everything
    assert alice.post("/mode", data={"theme": "dark"}).status_code == 303
    assert len(buttons(alice.get("/dashboard").text)) == 3


# ---- the route -------------------------------------------------------------------------------


@pytest.mark.parametrize("mode", THEMES)
def test_a_signed_in_person_s_mode_is_saved(alice, app, mode):
    r = alice.post("/mode", data={"theme": mode, "next": "/guide"})
    assert r.status_code == 303 and r.headers["location"] == "/guide"
    assert user_of(app).theme == mode and alice.cookies.get("theme") == mode
    assert f'data-theme="{mode}"' in alice.get("/guide").text


def test_the_background_request_gets_a_short_answer_and_no_redirect(alice, app):
    r = alice.post("/mode", data={"theme": "dark"}, headers={"accept": "application/json"})
    assert r.status_code == 200 and r.json() == {"theme": "dark"}
    assert user_of(app).theme == "dark" and alice.cookies.get("theme") == "dark"


def test_a_visitor_gets_a_cookie_and_nothing_is_stored(make_client, app):
    visitor = make_client()
    visitor.post("/mode", data={"theme": "dark"})
    assert visitor.cookies.get("theme") == "dark"
    assert 'data-theme="dark"' in visitor.get("/login").text
    with app.state.session_factory() as db:
        assert db.query(User).count() == 0


def test_an_unknown_mode_is_refused_and_changes_nothing(alice, app):
    alice.post("/mode", data={"theme": "dark"})
    for bad in ("neon", "", "DARK", "dark;x"):
        assert alice.post("/mode", data={"theme": bad}).status_code in (400, 422), bad
    assert user_of(app).theme == "dark" and alice.cookies.get("theme") == "dark"


@pytest.mark.parametrize("target", ["https://evil.example", "//evil.example", "/a\\b", ""])
def test_it_never_sends_people_to_another_site(alice, target):
    r = alice.post("/mode", data={"theme": "light", "next": target})
    assert r.status_code == 303 and r.headers["location"] == "/"


def test_it_leaves_the_colour_scheme_alone(alice, app):
    alice.post("/account/theme", data={"theme": "system", "scheme": "neon"})
    alice.post("/mode", data={"theme": "dark"})
    assert user_of(app).color_scheme == "neon" and user_of(app).theme == "dark"
    assert 'data-theme="dark" data-scheme="neon"' in alice.get("/dashboard").text


def test_the_account_page_radios_show_the_mode_chosen_with_the_switch(alice):
    alice.post("/mode", data={"theme": "light"})
    page = alice.get("/account").text
    assert re.search(r'name="theme" value="light" checked', page)


def test_the_cookie_is_set_safely(alice):
    header = alice.post("/mode", data={"theme": "dark"}).headers["set-cookie"].lower()
    assert "httponly" in header and "samesite=lax" in header and "max-age=31536000" in header


# ---- the script ------------------------------------------------------------------------------


def test_the_script_is_loaded_on_every_page_with_a_version(make_client):
    page = make_client().get("/").text
    assert re.search(r'<script src="/static/mode\.js\?v=\w+" defer>', page)


def test_the_script_changes_the_page_saves_it_and_supports_the_keyboard(make_client):
    js = make_client().get("/static/mode.js").text
    assert "dataset.theme = mode" in js and "fetch('/mode'" in js and "application/json" in js
    for key in ("ArrowRight", "ArrowLeft", "Home", "End"):
        assert key in js
    assert 'input[type="radio"][name="theme"]' in js  # the Account page radios stay in step
    assert "aria-checked" in js and "tabIndex" in js


def test_the_version_in_the_address_follows_the_script_so_browsers_never_use_an_old_copy():
    from app import templating
    with_mode = templating._version("app.js", "mode.js")
    assert with_mode != templating._version("app.js")  # the script is part of the version
    assert templates.env.globals["js_version"] == templating._version(
        "app.js", "datetime-picker.js", "photo-editor.js", "tags.js", "back.js", "utm.js",
        "mode.js")


# ---- how it looks ----------------------------------------------------------------------------


def rule(selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    assert match, selector
    return match.group(1)


def test_the_buttons_are_big_enough_to_tap_and_use_theme_colours_only():
    button = rule(".modeswitch button")
    assert "width: 44px" in button and "height: 40px" in button
    block = " ".join(rule(s) for s in (".modeswitch", ".modeswitch button", ".modeswitch button.on",
                                       ".modeswitch button:hover"))
    assert "#" not in block  # every colour comes from the theme variables
    assert "var(--accent)" in rule(".modeswitch button.on") and "var(--accent2)" in rule(
        ".modeswitch button.on")
    assert "box-shadow: var(--glow)" in rule(".modeswitch button.on")  # the glow of Neon


def test_the_switch_has_a_visible_focus_ring_and_shrinks_a_little_on_small_phones():
    assert "outline: 2px solid var(--accent)" in rule(".modeswitch button:focus-visible")
    assert re.search(r"@media \(max-width: 480px\) \{ \.modeswitch button \{ width: 38px", CSS)
