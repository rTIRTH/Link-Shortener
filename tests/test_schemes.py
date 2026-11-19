"""Colour schemes (Classic and Neon): new colours for the light and the dark mode, nothing moved."""

import colorsys
import re
from pathlib import Path

import pytest
import tinycss2

from app import features
from app.models import User
from app.profile import SCHEMES, THEMES

CSS = (Path(__file__).resolve().parent.parent / "app" / "static" / "style.css").read_text(
    encoding="utf-8")
PW = "password123"
LOOKS = {
    "light": ':root[data-scheme="{s}"]:not([data-theme="dark"]) {{',
    "dark": ':root[data-scheme="{s}"][data-theme="dark"] {{',
    "system in a dark browser": ':root[data-scheme="{s}"][data-theme="system"] {{',
}
NEW = ("classic", "neon")
TEXT_ON = [
    ("ink", "paper"), ("ink", "card"), ("ink", "field"), ("ink", "hover"),
    ("muted", "paper"), ("muted", "card"), ("muted", "head"), ("muted", "hover"),
    ("accent", "paper"), ("accent", "card"), ("accent-ink", "accent"), ("accent-ink", "accent2"),
    ("danger", "card"), ("ok", "ok-bg"), ("danger", "err-bg"), ("warn", "warn-bg"),
]


def block_text(selector: str) -> str:
    start = CSS.index(selector)
    return CSS[start:CSS.index("}", start)]


def palette(selector: str) -> dict:
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", block_text(selector)))


def look(scheme: str, mode: str) -> dict:
    return palette(LOOKS[mode].format(s=scheme))


def luminance(colour: str) -> float:
    r, g, b = (int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lin = [c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4 for c in (r, g, b)]
    return .2126 * lin[0] + .7152 * lin[1] + .0722 * lin[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + .05) / (lo + .05)


def hue(colour: str) -> float:
    r, g, b = (int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hsv(r, g, b)[0] * 360


def user_of(app, name="alice") -> User:
    with app.state.session_factory() as db:
        return db.query(User).filter_by(username=name).one()


def save(client, theme="system", **extra):
    return client.post("/account/theme", data={"theme": theme, **extra})


# ---- the colours ---------------------------------------------------------------------------------


def test_the_schemes_are_default_classic_and_neon():
    assert SCHEMES == ("default", "classic", "neon") and THEMES == ("system", "light", "dark")


@pytest.mark.parametrize("scheme", NEW)
@pytest.mark.parametrize("mode", list(LOOKS))
def test_every_scheme_has_a_complete_look_for_every_mode(scheme, mode):
    complete = set(palette(':root[data-theme="dark"] {'))  # every colour the default theme has
    assert set(look(scheme, mode)) == complete


@pytest.mark.parametrize("scheme", NEW)
@pytest.mark.parametrize("mode", list(LOOKS))
def test_text_is_easy_to_read_in_every_scheme_and_mode(scheme, mode):
    colours = look(scheme, mode)
    for text, background in TEXT_ON:
        ratio = contrast(colours[text], colours[background])
        assert ratio >= 4.5, f"{scheme} {mode}: {text} on {background} is only {ratio:.2f}:1"
    assert contrast(colours["field-line"], colours["card"]) >= 3.0  # input outlines stay visible


@pytest.mark.parametrize("scheme", NEW)
def test_dark_and_system_in_a_dark_browser_are_identical(scheme):
    dark = block_text(LOOKS["dark"].format(s=scheme)).split("{", 1)[1]
    system = block_text(LOOKS["system in a dark browser"].format(s=scheme)).split("{", 1)[1]
    assert re.sub(r"\s+", " ", dark).strip() == re.sub(r"\s+", " ", system).strip()


@pytest.mark.parametrize("scheme", NEW)
def test_light_is_really_light_and_dark_is_really_dark(scheme):
    assert luminance(look(scheme, "light")["paper"]) > 0.6
    assert luminance(look(scheme, "dark")["paper"]) < 0.05
    assert "color-scheme: light" in block_text(LOOKS["light"].format(s=scheme))
    assert "color-scheme: dark" in block_text(LOOKS["dark"].format(s=scheme))


@pytest.mark.parametrize("scheme", NEW)
def test_the_light_looks_have_no_glaring_pure_white_surfaces(scheme):
    light = look(scheme, "light")
    for surface in ("paper", "card", "field", "head", "hover"):
        assert light[surface].lower() != "#ffffff"
    assert max(int(light["card"][i:i + 2], 16) for i in (1, 3, 5)) <= 0xFC


@pytest.mark.parametrize("scheme", NEW)
@pytest.mark.parametrize("mode", list(LOOKS))
def test_the_accents_stay_blue_and_purple(scheme, mode):
    colours = look(scheme, mode)
    assert 210 <= hue(colours["accent"]) <= 245, colours["accent"]  # blue
    assert 255 <= hue(colours["accent2"]) <= 285, colours["accent2"]  # purple


def test_neon_has_a_glow_and_classic_has_none():
    for mode in LOOKS:
        neon = block_text(LOOKS[mode].format(s="neon")).replace("\n", " ")
        classic = block_text(LOOKS[mode].format(s="classic")).replace("\n", " ")
        assert "--glow: none" not in neon  # a glow in the light look too, a softer one
        assert "--glow: none; --text-glow: none; --bar-glow: none" in classic
    dark = block_text(LOOKS["dark"].format(s="neon"))
    assert re.search(r"--glow: 0 0 16px", dark) and "--text-glow: 0 0 16px" in dark


# ---- nothing moves ---------------------------------------------------------------------------

ALLOWED = {"color-scheme", "box-shadow", "text-shadow", "filter"}


def scheme_rules():
    found = []
    stack = tinycss2.parse_stylesheet(CSS, skip_whitespace=True, skip_comments=True)
    for rule in stack:
        if rule.type == "at-rule" and rule.content:
            stack_inner = tinycss2.parse_rule_list(rule.content, skip_whitespace=True,
                                                   skip_comments=True)
            found += [r for r in stack_inner if r.type == "qualified-rule"
                      and "data-scheme" in tinycss2.serialize(r.prelude)]
        elif rule.type == "qualified-rule" and "data-scheme" in tinycss2.serialize(rule.prelude):
            found.append(rule)
    return found


def test_scheme_rules_only_touch_colours_and_shadows_never_layout():
    rules = scheme_rules()
    assert len(rules) >= 9  # 3 looks x 2 schemes, plus the neon glow rules
    for rule in rules:
        declarations = tinycss2.parse_declaration_list(
            rule.content, skip_whitespace=True, skip_comments=True)
        for item in declarations:
            assert item.type == "declaration", tinycss2.serialize(rule.prelude)
            assert item.name.startswith("--") or item.name in ALLOWED, (
                f"{tinycss2.serialize(rule.prelude).strip()} sets {item.name}")


def test_the_scheme_blocks_set_only_variables():
    for rule in scheme_rules():
        prelude = tinycss2.serialize(rule.prelude)
        if "data-theme" in prelude:  # the colour blocks
            names = [d.name for d in tinycss2.parse_declaration_list(
                rule.content, skip_whitespace=True, skip_comments=True) if d.type == "declaration"]
            assert all(n.startswith("--") or n == "color-scheme" for n in names), prelude


def test_the_default_look_has_no_scheme_rules_so_it_is_untouched():
    assert 'data-scheme="default"' not in CSS
    root = CSS[CSS.index(":root {"):CSS.index("}", CSS.index(":root {"))]
    assert "--glow: none; --text-glow: none; --bar-glow: none; --backdrop: none;" in root
    assert re.search(r"body \{[^}]*background: var\(--backdrop\) fixed no-repeat, var\(--paper\)",
                     CSS)


def test_no_box_is_moved_by_a_scheme_the_page_html_is_the_same(alice, app):
    alice.post("/dashboard/links", data={"original_url": "https://example.com/a", "slug": "one"})
    alice.get("/dashboard")  # show the "Created" message once, so it is not in the comparison
    paths = ["/dashboard", "/dashboard/links/1", "/dashboard/links/1/edit", "/guide",
             "/dashboard/links/import"]
    before = {p: alice.get(p).text for p in paths}
    save(alice, scheme="neon")
    alice.get("/account")  # same for "Appearance saved."
    for path in paths:
        after = alice.get(path).text
        assert after.replace('data-scheme="neon"', 'data-scheme="default"') == before[path], path
        assert 'data-scheme="neon"' in after


# ---- choosing a scheme -----------------------------------------------------------------------


def test_everybody_starts_on_the_default_scheme(make_client, alice, app):
    assert user_of(app).color_scheme == "default"
    assert 'data-scheme="default"' in alice.get("/dashboard").text
    assert 'data-scheme="default"' in make_client().get("/login").text


@pytest.mark.parametrize("scheme", ["classic", "neon"])
def test_a_scheme_is_saved_and_applied_with_any_mode(alice, app, scheme):
    for mode in ("light", "dark", "system"):
        save(alice, mode, scheme=scheme)
        page = alice.get("/dashboard").text
        assert f'data-theme="{mode}" data-scheme="{scheme}"' in page
    assert user_of(app).color_scheme == scheme and user_of(app).theme == "system"


def test_saving_only_the_mode_keeps_the_scheme(alice, app):
    save(alice, "dark", scheme="neon")
    save(alice, "light")  # the form was sent without a scheme
    assert user_of(app).theme == "light" and user_of(app).color_scheme == "neon"


def test_going_back_to_the_default_scheme(alice, app):
    save(alice, scheme="neon")
    save(alice, scheme="default")
    assert user_of(app).color_scheme == "default"


def test_an_unknown_scheme_is_refused_and_changes_nothing(alice, app):
    save(alice, "dark", scheme="neon")
    r = save(alice, "light", scheme="rainbow")
    assert r.status_code == 303
    assert "Unknown colour scheme." in alice.get("/account").text
    assert user_of(app).theme == "dark" and user_of(app).color_scheme == "neon"


def test_a_scheme_name_is_not_a_mode(alice, app):
    save(alice, "neon")  # "neon" is a colour scheme, not a light/dark mode
    assert user_of(app).theme == "system" and user_of(app).color_scheme == "default"


def test_the_cookie_gives_logged_out_pages_the_same_colours(alice):
    save(alice, "dark", scheme="classic")
    assert alice.cookies.get("scheme") == "classic"
    alice.post("/logout")
    page = alice.get("/login").text
    assert 'data-theme="dark" data-scheme="classic"' in page


def test_a_bad_cookie_means_the_default(make_client):
    visitor = make_client()
    visitor.cookies.set("scheme", "<script>")
    assert 'data-scheme="default"' in visitor.get("/login").text


def test_signing_in_brings_the_saved_scheme_back(alice):
    save(alice, "light", scheme="neon")
    alice.post("/logout")
    alice.cookies.clear()
    assert 'data-scheme="default"' in alice.get("/login").text
    alice.post("/login", data={"identifier": "alice", "password": PW})
    assert alice.cookies.get("scheme") == "neon"
    assert 'data-scheme="neon"' in alice.get("/dashboard").text


def test_a_new_account_inherits_the_scheme_chosen_before_signing_up(make_client, app):
    visitor = make_client()
    visitor.cookies.set("scheme", "classic")
    visitor.post("/register", data={"username": "newbie", "email": "n@example.com",
                                    "password": PW})
    assert user_of(app, "newbie").color_scheme == "classic"


# ---- the picker on the account page ----------------------------------------------------------


def scheme_box(page: str) -> str:
    start = page.index('class="theme-grid scheme-grid"')
    return page[start:page.index("</fieldset>", start)]


def test_the_account_page_offers_the_three_schemes_under_the_modes(alice):
    page = alice.get("/account").text
    box = scheme_box(page)
    assert re.findall(r'name="scheme" value="(\w+)"', box) == ["default", "classic", "neon"]
    for label in ("Default", "Classic", "Neon", "The original blues", "Soft blue and violet",
                  "Glowing blue and purple"):
        assert label in box
    assert box.count('class="dots dots-') == 3
    assert page.index('name="theme" value="dark"') < page.index('name="scheme" value="default"')
    assert page.index('name="scheme" value="neon"') < page.index("Save appearance")  # one form


def test_the_current_scheme_is_the_checked_one(alice):
    save(alice, scheme="classic")
    box = scheme_box(alice.get("/account").text)
    assert re.search(r'value="classic" checked', box)
    assert not re.search(r'value="(default|neon)" checked', box)


def test_picking_a_scheme_shows_it_straight_away(alice):
    assert "dataset.scheme = r.value" in alice.get("/account").text


def test_the_existing_mode_picker_is_unchanged(alice):
    page = alice.get("/account").text
    start = page.index('class="theme-grid"')
    modes = page[start:page.index("</fieldset>", start)]
    assert re.findall(r'name="theme" value="(\w+)"', modes) == ["system", "light", "dark"]


# ---- the paid-plan gate ----------------------------------------------------------------------


def test_locked_schemes_are_disabled_with_a_note(alice, monkeypatch):
    monkeypatch.setattr(features, "PAID", frozenset({"color_schemes"}))
    page = alice.get("/account").text
    box = scheme_box(page)
    assert re.search(r'value="default" (?!disabled)', box)
    assert re.search(r'value="classic" [^>]*disabled', box)
    assert re.search(r'value="neon" [^>]*disabled', box)
    assert "paid plan" in page


def test_a_locked_scheme_cannot_be_posted_but_modes_and_default_still_work(
        alice, app, monkeypatch):
    monkeypatch.setattr(features, "PAID", frozenset({"color_schemes"}))
    save(alice, "dark", scheme="neon")
    assert user_of(app).color_scheme == "default"
    assert "paid plan" in alice.get("/account").text
    save(alice, "dark", scheme="default")
    assert user_of(app).theme == "dark"
    save(alice, "light")
    assert user_of(app).theme == "light"


def test_a_scheme_chosen_earlier_keeps_working_when_it_becomes_paid(alice, app, monkeypatch):
    save(alice, scheme="neon")
    monkeypatch.setattr(features, "PAID", frozenset({"color_schemes"}))
    assert 'data-scheme="neon"' in alice.get("/dashboard").text
    save(alice, "dark", scheme="neon")  # saving the one they already have is not a change
    assert user_of(app).color_scheme == "neon" and user_of(app).theme == "dark"
    save(alice, "dark", scheme="classic")
    assert user_of(app).color_scheme == "neon"


# ---- languages and the database --------------------------------------------------------------


@pytest.mark.parametrize("lang, texts", [
    ("hi", ["रंग योजना", "क्लासिक", "नियॉन"]), ("gu", ["રંગ યોજના", "ક્લાસિક", "નિયૉન"]),
])
def test_the_picker_is_translated(alice, lang, texts):
    alice.post("/language", data={"lang": lang, "next": "/"})
    box = scheme_box(alice.get("/account").text)
    assert all(t in box for t in texts)
    for english in ("Classic", "Neon", "Soft blue and violet"):
        assert english not in box


def test_the_migration_adds_the_column_for_everyone_with_the_default():
    text = Path("alembic/versions/0013_color_scheme.py").read_text(encoding="utf-8")
    assert "'color_scheme'" in text and "server_default='default'" in text
    assert "down_revision = '0012'" in text and hasattr(User, "color_scheme")
