"""Guards for the look of the buttons (there is no browser in the test run, so check the CSS)."""
import re
from pathlib import Path

import tinycss2

APP = Path(__file__).resolve().parent.parent / "app"
CSS = (APP / "static" / "style.css").read_text(encoding="utf-8")


def rule_for(selector: str) -> str:
    """The declarations of the first rule whose selector list contains `selector`."""
    for rule in tinycss2.parse_stylesheet(CSS, skip_whitespace=True, skip_comments=True):
        if rule.type == "qualified-rule":
            selectors = [s.strip() for s in tinycss2.serialize(rule.prelude).split(",")]
            if selector in selectors:
                return tinycss2.serialize(rule.content)
    raise AssertionError(f"no rule for {selector}")


def test_css_parses_without_errors():
    rules = tinycss2.parse_stylesheet(CSS, skip_whitespace=True, skip_comments=True)
    assert not [r for r in rules if r.type == "error"]


def test_every_kind_of_button_gets_the_same_thin_outline():
    ring = rule_for(".btn::before")
    for selector in (".lang-btn::before", ".dtp-nav::before", ".dtp-period::before",
                     ".avatar-btn::before"):
        assert rule_for(selector) == ring  # one shared rule
    assert "padding: var(--ring)" in ring and "var(--edge)" in ring   # thickness + gradient colour
    assert re.search(r"--ring:\s*1\.5px", rule_for(":root"))          # a little thicker than 1px
    assert "mask-composite" in ring                                # only the ring, not the fill


def test_old_thick_or_plain_borders_are_gone():
    assert "border: 2px" not in rule_for(".langmenu summary.lang-btn")
    assert "border: 1px solid transparent" in rule_for(".langmenu summary.lang-btn")
    for selector in (".btn", ".dtp-nav", ".dtp-period"):
        declarations = rule_for(selector)
        assert "border: 1px solid transparent" in declarations, selector
        assert "position: relative" in declarations, selector      # the ring is placed inside it
    assert "border: 0" in rule_for(".menu summary .avatar")


def test_delete_buttons_keep_a_red_outline():
    for selector in (".btn.danger", ".btn.danger-solid"):
        assert "--edge: var(--edge-danger)" in rule_for(selector)
    assert "var(--danger)" in CSS


def test_outline_colours_exist_in_every_theme():
    assert "--accent2" in rule_for(":root")
    assert CSS.count("--accent2:") == 3  # light, dark, and "system" in a dark browser


def test_profile_icon_uses_the_outline(alice):
    page = alice.get("/dashboard").text
    assert 'class="avatar-btn"' in page


def test_ordinary_buttons_keep_the_blue_to_purple_gradient_outline():
    root = rule_for(":root")
    assert re.search(r"--edge:\s*linear-gradient", root)
    assert re.search(r"--edge-danger:\s*linear-gradient", root)
    assert "inset: -1px" in rule_for(".btn::before")     # tight ring, no floating halo
    assert "inset: -5px" not in CSS


def test_filled_buttons_have_no_outline_but_outlined_ones_do(alice):
    filled = rule_for(".btn:not(.ghost):not(.danger)::before")
    assert "display: none" in filled
    assert "display: none" in rule_for('.dtp-period[aria-pressed="true"]::before')
    assert "display: none" not in rule_for(".btn::before")      # the shared outline stays on
    assert "btn-plain" not in CSS and "btn-purple" not in CSS    # one-off experiments are gone
    # the buttons from the settings page are plain "btn" buttons, so the rule above covers them
    account = alice.get("/account").text
    for label in ("Save avatar", "Change username", "Change password", "Save appearance"):
        pattern = rf'<button class="btn" type="submit">\s*{label}\s*</button>'
        assert re.search(pattern, account), label
    assert 'class="btn danger-solid"' in account  # Delete my account: filled too
    assert "btn ghost small" in account  # Log out: outlined, keeps its ring
    assert "btn-plain" not in alice.get("/dashboard").text


def test_avatar_grid_always_ends_on_a_full_row():
    """The picker is 9, 6 or 4 columns wide; the avatar count must divide by each."""
    from app.profile import AVATARS

    assert "repeat(9, 1fr)" in rule_for(".avatar-grid")
    assert "repeat(6, 1fr)" in CSS and "repeat(4, 1fr)" in CSS
    for columns in (9, 6, 4):
        gap = f"{len(AVATARS)} avatars leave a gap with {columns} columns"
        assert len(AVATARS) % columns == 0, gap


# ---- colours: both themes must stay easy to read -------------------------------------------


def palette(selector: str) -> dict:
    """The --colour variables of one theme block, e.g. {"ink": "#1b2536", ...}."""
    start = CSS.index(selector)
    block = CSS[start:CSS.index("}", start)]
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", block))


def contrast(a: str, b: str) -> float:
    def luminance(colour: str) -> float:
        r, g, b_ = (int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
        lin = [c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4 for c in (r, g, b_)]
        return .2126 * lin[0] + .7152 * lin[1] + .0722 * lin[2]

    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + .05) / (lo + .05)


THEMES = {
    "light": ":root {",
    "dark": ':root[data-theme="dark"] {',
    "system in a dark browser": ':root[data-theme="system"] {',
}
TEXT_ON = [  # (text colour, background) pairs that must reach 4.5:1 (WCAG AA for normal text)
    ("ink", "paper"), ("ink", "card"), ("ink", "field"), ("ink", "hover"),
    ("muted", "paper"), ("muted", "card"), ("muted", "head"), ("muted", "hover"),
    ("accent", "paper"), ("accent", "card"), ("accent-ink", "accent"),
    ("danger", "card"), ("ok", "ok-bg"), ("danger", "err-bg"), ("warn", "warn-bg"),
]


def test_text_is_readable_in_every_theme():
    for name, selector in THEMES.items():
        colours = palette(selector)
        for text, background in TEXT_ON:
            ratio = contrast(colours[text], colours[background])
            assert ratio >= 4.5, f"{name}: {text} on {background} is only {ratio:.2f}:1"


def test_input_boxes_have_a_visible_outline_in_every_theme():
    for name, selector in THEMES.items():
        colours = palette(selector)
        ratio = contrast(colours["field-line"], colours["card"])
        assert ratio >= 3.0, f"{name}: input outline is only {ratio:.2f}:1 against the card"


def test_the_light_theme_is_not_glaring():
    """No pure white page or card: soft surfaces are easier on the eyes."""
    light = palette(":root {")
    for surface in ("paper", "card", "field", "head", "hover"):
        assert light[surface].lower() != "#ffffff", surface
    assert max(int(light["card"][i:i + 2], 16) for i in (1, 3, 5)) <= 0xFC  # not near-white


def test_dark_theme_and_system_dark_use_the_same_colours():
    assert palette(THEMES["dark"]) == palette(THEMES["system in a dark browser"])
    assert set(palette(THEMES["light"])) == set(palette(THEMES["dark"]))  # nothing missing
