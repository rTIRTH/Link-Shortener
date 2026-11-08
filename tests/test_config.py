"""The database address: hosts give it in different shapes and the app must accept all of them."""
from app.config import _normalize_db_url
from app.database import make_session_factory


def test_postgres_addresses_get_the_right_driver():
    for start in ("postgres://", "postgresql://"):
        assert _normalize_db_url(f"{start}u:p@host/db").startswith("postgresql+psycopg2://u:p@host/db")
    assert _normalize_db_url("postgresql+psycopg2://u:p@host/db") == "postgresql+psycopg2://u:p@host/db"
    assert _normalize_db_url("sqlite:///./x.db") == "sqlite:///./x.db"


def test_neon_addresses_are_made_secure_when_the_setting_is_missing():
    bare = "postgresql://u:p@ep-cool-1234.us-east-2.aws.neon.tech/neondb"
    assert _normalize_db_url(bare).endswith("/neondb?sslmode=require")
    with_other = bare + "?channel_binding=require"
    assert _normalize_db_url(with_other).endswith("?channel_binding=require&sslmode=require")


def test_neon_addresses_that_already_say_so_are_left_alone():
    url = "postgresql://u:p@ep-1-pooler.eu-west-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    assert _normalize_db_url(url) == url.replace("postgresql://", "postgresql+psycopg2://")


def test_other_hosts_are_not_changed():
    assert "sslmode" not in _normalize_db_url("postgresql://u:p@dpg-123/db")
    # a password that merely contains the word neon.tech must not trigger it
    assert "sslmode" not in _normalize_db_url("postgresql://u:neon.tech@dpg-123/db")


def test_postgres_connections_survive_a_sleeping_database():
    factory = make_session_factory("postgresql+psycopg2://u:p@localhost/db")  # connects later
    engine = factory.kw["bind"]
    assert engine.pool._pre_ping is True and engine.pool._recycle == 300
