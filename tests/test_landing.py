"""The home page (before login) lists what the app can do, in every language."""

import re

import pytest

from app.i18n import translate

CARDS = [
    "Custom aliases", "Click analytics", "Activity log", "Hour by hour", "Compare links",
    "Schedule links", "On and off", "Edit any time", "Password protection", "QR codes",
    "Your data", "Your language",
]


def titles(page):
    return re.findall(r"<h3>([^<]*)</h3>", page)


def test_home_lists_every_feature(client):
    page = client.get("/").text
    assert titles(page) == CARDS
    assert "compare their clicks in one graph" in page
    assert "Deactivate a link in one click" in page
    assert "hour by hour" in page and "Ask visitors for a password" in page


@pytest.mark.parametrize("lang", ["hi", "gu"])
def test_home_features_are_translated(client, lang):
    client.post("/language", data={"lang": lang, "next": "/"})
    page = client.get("/").text
    assert titles(page) == [translate(lang, c) for c in CARDS]
    assert not any(c in page for c in CARDS if c not in ("Your data",))
    assert len(set(titles(page))) == 12  # twelve different cards
