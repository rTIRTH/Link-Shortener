import fakeredis
import pytest
from fastapi.testclient import TestClient

from app import cache
from app.database import Base
from app.main import create_app


@pytest.fixture()
def app():
    app = create_app("sqlite://")  # in-memory database, fresh for every test
    engine = app.state.session_factory.kw["bind"]
    Base.metadata.create_all(engine)
    return app


@pytest.fixture()
def redis_fake():
    fake = fakeredis.FakeRedis(decode_responses=True)
    cache._client = fake
    yield fake
    cache._client = None


@pytest.fixture()
def client(app):
    return TestClient(app, follow_redirects=False)


def register(client, username="alice", email=None, password="password123"):
    return client.post("/register", data={
        "username": username, "email": email or f"{username}@example.com", "password": password,
    })


@pytest.fixture()
def alice(client):
    register(client, "alice")
    return client


@pytest.fixture()
def make_client(app):
    def _make():
        return TestClient(app, follow_redirects=False)
    return _make


@pytest.fixture(autouse=True)
def _reset_local_rate_limits():
    cache._local.clear()
    yield
    cache._local.clear()
