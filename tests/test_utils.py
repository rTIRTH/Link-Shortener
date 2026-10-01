import pytest

from app.utils import (
    csv_safe,
    generate_slug,
    parse_device,
    validate_slug,
    validate_url,
    validate_username,
)


def test_generate_slug_length_and_charset():
    slug = generate_slug(8)
    assert len(slug) == 8 and slug.isalnum()


def test_generate_slug_is_random():
    assert len({generate_slug() for _ in range(200)}) == 200


@pytest.mark.parametrize("raw,expected", [
    ("example.com", "https://example.com"),
    ("  http://example.com/a?b=1  ", "http://example.com/a?b=1"),
])
def test_validate_url_ok(raw, expected):
    assert validate_url(raw) == expected


@pytest.mark.parametrize("raw", [
    "", "javascript:alert(1)", "ftp://example.com", "http://localhost:8000",
    "http://127.0.0.1", "http://192.168.1.5/x", "http://nodots", "has space.com",
    "http://example.com:99999", "https://" + "a" * 2100 + ".com",
])
def test_validate_url_rejects(raw):
    with pytest.raises(ValueError):
        validate_url(raw)


def test_validate_url_blocks_own_host():
    with pytest.raises(ValueError):
        validate_url("https://shortener.test/x", blocked_hosts=("shortener.test",))


def test_slug_and_username_rules():
    assert validate_slug("my-link_1") == "my-link_1"
    with pytest.raises(ValueError):
        validate_slug("a")
    with pytest.raises(ValueError):
        validate_username("dashboard")
    with pytest.raises(ValueError):
        validate_username("Bad Name!")
    assert validate_username("  Alice_1 ") == "alice_1"


def test_parse_device():
    assert parse_device("Mozilla/5.0 (iPhone; CPU iPhone OS 17) Mobile") == "mobile"
    assert parse_device("Mozilla/5.0 (iPad; CPU OS 17)") == "tablet"
    assert parse_device("Googlebot/2.1") == "bot"
    assert parse_device("Mozilla/5.0 (Windows NT 10.0; Win64)") == "desktop"
    assert parse_device(None) == "desktop"


def test_csv_safe():
    assert csv_safe("=SUM(A1)") == "'=SUM(A1)"
    assert csv_safe("normal") == "normal"
