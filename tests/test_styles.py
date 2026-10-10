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


def test_outline_is_one_solid_purple_all_the_way_round():
    root = rule_for(":root")
    assert re.search(r"--edge:\s*var\(--accent2\)\s*;", root)          # no gradient
    assert "gradient" not in re.search(r"--edge:[^;]*;", root).group(0)
    assert re.search(r"--accent2:\s*#9333ea", root)                      # purple on light
    assert CSS.count("#b66dff") >= 2                                       # brighter purple on dark
    # filled buttons use the same tight ring, so it shows against the blue fill
    assert "inset: -1px" in rule_for(".btn::before")
    assert "inset: -5px" not in CSS and "floats" not in CSS


def test_delete_buttons_have_a_solid_red_outline():
    assert re.search(r"--edge-danger:\s*var\(--danger\)\s*;", rule_for(":root"))
