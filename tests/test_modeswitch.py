"""The small light / system default / dark button in the top bar, and the plain language pill."""

import re
from pathlib import Path

import pytest

from app import features, templating
from app.models import User
from app.profile import THEMES
from app.templating import templates

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
CSS = (STATIC / "style.css").read_text(encoding="utf-8")
NEXT = {"light": "system", "system": "dark", "dark": "light"}  # the order a tap goes in
NAMES = {"light": "Light", "system": "System default", "dark": "Dark"}


def user_of(app, name="alice") -> User:
    with app.state.session_factory() as db:
        return db.query(User).filter_by(username=name).one()


def form(page: str) -> str:
    start = page.index('<form class="modebtn-form"')
    return page[start:page.index("</form>", start)]


def button(page: str) -> dict:
    box = form(page)
    tag = re.search(r'<button type="submit" class="modebtn"([^>]*)>', box, re.S).group(1)
    pairs = re.findall(r'([\w-]+)=(?:"([^"]*)"|\'([^\']*)\')', tag)
    return {name: double or single for name, double, single in pairs}


def rule(selector: str) -> str:
    match = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    assert match, selector
    return match.group(1)


# ---- the button on every page --------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/", "/login", "/register", "/guide"])
def test_visitors_see_one_small_button_in_the_top_bar(make_client, path):
    page = make_client().get(path).text
    assert page.count('class="modebtn"') == 1 and "modeswitch" not in page  # not the 3-part switch
    assert 'action="/mode"' in form(page)


def test_signed_in_pages_have_it_too(alice):
    for path in ("/dashboard", "/account", "/guide"):
        assert alice.get(path).text.count('class="modebtn"') == 1, path


@pytest.mark.parametrize("mode", THEMES)
def test_the_button_names_the_mode_and_asks_for_the_next_one(alice, mode):
    alice.post("/mode", data={"theme": mode})
    attrs = button(alice.get("/dashboard").text)
    assert attrs["value"] == NEXT[mode]  # what a tap chooses
    expected = f"Colour mode: {NAMES[mode]}. Tap to switch to {NAMES[NEXT[mode]]}."
    assert attrs["aria-label"] == expected and attrs["title"] == expected


def test_a_tap_goes_light_then_system_default_then_dark_then_light_again():
    assert NEXT == {"light": "system", "system": "dark", "dark": "light"}
    seen, mode = [], "light"
    for _ in range(4):
        seen.append(mode)
        mode = NEXT[mode]
    assert seen == ["light", "system", "dark", "light"]


def test_the_button_carries_what_the_script_needs(make_client):
    attrs = button(make_client().get("/").text)
    assert attrs["data-aria"] == "Colour mode: {mode}. Tap to switch to {next}."
    assert re.search(r'"light":\s*"Light"', attrs["data-names"].replace("&#34;", '"'))
    assert "System default" in attrs["data-names"] and "Dark" in attrs["data-names"]


def test_it_has_the_three_icons_and_a_spoken_status(make_client):
    box = form(make_client().get("/").text)
    icons = re.findall(r'<svg class="ico (i-\w+)"', box)
    assert icons == ["i-light", "i-system", "i-dark"]  # sun, monitor, moon; one is shown
    assert 'role="status" aria-live="polite" data-mode-status' in box
    assert 'class="sr-only"' in box


def test_the_button_sits_after_the_nav_links_and_before_the_language_pill_and_avatar(alice):
    page = alice.get("/dashboard").text
    assert page.index('class="brand"') < page.index('class="modebtn-form"')
    assert page.index('class="modebtn-form"') < page.index('id="langmenu"')
    assert page.index('id="langmenu"') < page.index('id="usermenu"')


def test_the_rest_of_the_top_bar_is_unchanged(make_client):
    page = make_client().get("/").text
    bar = page[page.index("<header"):page.index("</header>")]
    assert 'class="brand"' in bar and 'href="/guide"' in bar and 'id="langmenu"' in bar
    assert 'href="/login"' in bar and 'href="/register"' in bar


@pytest.mark.parametrize("lang, mode_word, tap_word", [
    ("hi", "रंग मोड", "टैप करें"), ("gu", "રંગ મોડ", "ટૅપ કરો"),
])
def test_the_button_speaks_each_language(make_client, lang, mode_word, tap_word):
    visitor = make_client()
    visitor.cookies.set("lang", lang)
    attrs = button(visitor.get("/").text)
    assert mode_word in attrs["aria-label"] and tap_word in attrs["aria-label"]
    assert "Light" not in attrs["aria-label"] and "System default" not in attrs["aria-label"]
    assert "{mode}" in attrs["data-aria"] and "{next}" in attrs["data-aria"]  # filled in later


def test_the_button_is_not_a_paid_feature(alice, monkeypatch):
    monkeypatch.setattr(features, "PAID", frozenset(features.FEATURES))  # lock everything
    assert alice.post("/mode", data={"theme": "dark"}).status_code == 303
    assert alice.get("/dashboard").text.count('class="modebtn"') == 1


# ---- the language button is a plain pill ---------------------------------------------------------


def test_the_language_button_is_just_the_language_name_in_a_pill(alice):
    page = alice.get("/dashboard").text
    start = page.index('<summary class="lang-btn"')
    summary = page[start:page.index("</summary>", start)]
    assert re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", summary)) == "English"
    assert "<svg" not in summary and "lang-icon" not in summary and "lang-chev" not in summary
    assert 'aria-label="Change language"' in summary  # still named for screen readers


def test_the_language_menu_still_works(alice):
    page = alice.get("/dashboard").text
    assert 'name="lang" value="hi"' in page and 'name="lang" value="gu"' in page
    assert 'name="next" value="/dashboard"' in page


def test_the_language_pill_is_drawn_in_the_accent_colour_with_the_shared_outline():
    pill = rule(".langmenu summary.lang-btn")
    assert "color: var(--accent)" in pill and "border-radius: 999px" in pill
    assert "border: 1px solid transparent" in pill  # the gradient ring is drawn over it
    assert "lang-icon" not in CSS and "lang-chev" not in CSS
    assert not re.search(r"\.lang-name\s*\{\s*display:\s*none", CSS)  # the name stays on phones


# ---- the route -----------------------------------------------------------------------------------


@pytest.mark.parametrize("mode", THEMES)
def test_a_signed_in_person_s_mode_is_saved(alice, app, mode):
    r = alice.post("/mode", data={"theme": mode, "next": "/guide"})
    assert r.status_code == 303 and r.headers["location"] == "/guide"
    assert user_of(app).theme == mode and alice.cookies.get("theme") == mode
    assert f'data-theme="{mode}"' in alice.get("/guide").text


def test_the_button_works_without_javascript_by_posting_its_own_value(alice, app):
    seen = []
    for _ in range(4):
        page = alice.get("/dashboard").text
        seen.append(re.search(r'data-theme="(\w+)"', page).group(1))
        alice.post("/mode", data={"theme": button(page)["value"], "next": "/dashboard"})
    assert seen == ["system", "dark", "light", "system"]  # starts on system, then each tap cycles


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


def test_the_account_page_no_longer_has_the_light_dark_cards(alice):
    page = alice.get("/account").text
    assert 'type="radio" name="theme"' not in page  # the top bar button changes the mode now
    for gone in ("Match my device", "Always light", "Always dark"):
        assert gone not in page
    assert "To switch between light and dark, use the button in the top bar." in page
    assert page.count('class="modebtn"') == 1  # and that button is on this page too


def test_the_account_page_keeps_the_colour_scheme_and_its_button(alice):
    page = alice.get("/account").text
    start = page.index('id="appearance"')
    panel = page[start:page.index("</section>", start)]
    assert re.findall(r'name="scheme" value="(\w+)"', panel) == ["default", "classic", "neon"]
    assert "Save appearance" in panel and 'action="/account/theme"' in panel


def test_saving_the_scheme_alone_keeps_the_mode(alice, app):
    alice.post("/mode", data={"theme": "dark"})
    r = alice.post("/account/theme", data={"scheme": "neon"})  # what the Account page sends
    assert r.status_code == 303
    assert "Appearance saved." in alice.get("/account").text
    assert user_of(app).color_scheme == "neon" and user_of(app).theme == "dark"
    assert alice.cookies.get("theme") == "dark" and alice.cookies.get("scheme") == "neon"


def test_saving_nothing_changes_nothing(alice, app):
    alice.post("/mode", data={"theme": "light"})
    alice.post("/account/theme", data={"scheme": "classic"})
    alice.post("/account/theme", data={})
    assert user_of(app).theme == "light" and user_of(app).color_scheme == "classic"


def test_the_mode_can_still_be_sent_to_the_account_form_and_is_checked(alice, app):
    alice.post("/account/theme", data={"theme": "dark", "scheme": "default"})
    assert user_of(app).theme == "dark"
    alice.post("/account/theme", data={"theme": "neon"})
    assert "Unknown theme." in alice.get("/account").text and user_of(app).theme == "dark"


def test_the_account_page_script_only_previews_the_colour_scheme(alice):
    page = alice.get("/account").text
    assert "dataset.scheme = r.value" in page and "dataset.theme = r.value" not in page


@pytest.mark.parametrize("lang, sentence", [
    ("hi", "लाइट और डार्क के बीच बदलने के लिए"), ("gu", "લાઇટ અને ડાર્ક વચ્ચે બદલવા માટે"),
])
def test_the_new_sentence_is_translated_and_the_old_card_texts_are_gone(alice, lang, sentence):
    from importlib import import_module
    alice.post("/language", data={"lang": lang, "next": "/"})
    assert sentence in alice.get("/account").text
    messages = import_module(f"app.locales.{lang}").MESSAGES
    for removed in ("Match my device", "Always light", "Always dark", "Theme"):
        assert removed not in messages


def test_the_cookie_is_set_safely(alice):
    header = alice.post("/mode", data={"theme": "dark"}).headers["set-cookie"].lower()
    assert "httponly" in header and "samesite=lax" in header and "max-age=31536000" in header


# ---- the script ----------------------------------------------------------------------------------


def test_the_script_is_loaded_on_every_page_with_a_version(make_client):
    page = make_client().get("/").text
    assert re.search(r'<script src="/static/mode\.js\?v=\w+" defer>', page)


def test_the_script_cycles_changes_the_page_saves_and_announces(make_client):
    js = make_client().get("/static/mode.js").text
    assert "['light', 'system', 'dark']" in js and "% ORDER.length" in js  # the tap order
    assert "dataset.theme = mode" in js and "fetch('/mode'" in js and "application/json" in js
    assert "data-mode-status" in js and "aria-label" in js
    assert 'name="theme"' not in js  # there are no mode radio buttons left to keep in step


def test_the_version_in_the_address_follows_the_script_so_browsers_never_use_an_old_copy():
    assert templating._version("app.js", "mode.js") != templating._version("app.js")
    assert templates.env.globals["js_version"] == templating._version(
        "app.js", "datetime-picker.js", "photo-editor.js", "tags.js", "back.js", "utm.js",
        "mode.js", "bulk.js")


# ---- how it looks --------------------------------------------------------------------------------


def test_the_button_is_a_44_pixel_circle_in_theme_colours_only():
    base = rule(".modebtn")
    assert "width: 44px" in base and "height: 44px" in base and "border-radius: 50%" in base
    assert "color: var(--accent)" in base and "background: var(--card)" in base
    for selector in (".modebtn", ".modebtn:hover, .modebtn:focus-visible"):
        assert "#" not in rule(selector), selector  # every colour comes from the theme variables


def test_hover_and_focus_draw_the_gradient_ring_and_the_neon_glow():
    hover = rule(".modebtn:hover, .modebtn:focus-visible")
    assert "var(--accent)" in hover and "var(--accent2)" in hover and "border-box" in hover
    assert "box-shadow: var(--glow)" in hover
    assert "outline: 2px solid var(--accent)" in rule(".modebtn:focus-visible")


def test_only_the_icon_of_the_current_mode_is_shown():
    assert "display: none" in rule(".modebtn .ico")
    shown = re.search(r'(:root\[data-theme="light"\][^{]*)\{\s*display:\s*block', CSS, re.S)
    assert shown
    for mode in THEMES:
        assert f':root[data-theme="{mode}"] .modebtn .i-{mode}' in shown.group(1)
