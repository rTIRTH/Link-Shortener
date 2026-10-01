from tests.conftest import register


def test_register_login_logout(client):
    r = register(client, "alice")
    assert r.status_code == 303 and r.headers["location"] == "/dashboard"
    assert client.get("/dashboard").status_code == 200

    client.post("/logout")
    assert client.get("/dashboard").status_code == 303  # sent to /login

    r = client.post("/login", data={"identifier": "ALICE@example.com", "password": "password123"})
    assert r.status_code == 303
    assert client.get("/dashboard").status_code == 200


def test_wrong_password(client):
    register(client, "alice")
    client.post("/logout")
    r = client.post("/login", data={"identifier": "alice", "password": "nope-nope"})
    assert r.status_code == 400 and "Wrong username" in r.text


def test_duplicate_and_invalid_registration(client):
    register(client, "alice")
    assert register(client, "alice", email="other@example.com").status_code == 400
    assert register(client, "bob", email="alice@example.com").status_code == 400
    assert register(client, "ab").status_code == 400
    assert register(client, "carol", password="short").status_code == 400
    assert register(client, "admin").status_code == 400


def test_dashboard_requires_login(client):
    r = client.get("/dashboard")
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_login_rate_limit(client, redis_fake):
    for _ in range(10):
        client.post("/login", data={"identifier": "x", "password": "y"})
    assert client.post("/login", data={"identifier": "x", "password": "y"}).status_code == 429
