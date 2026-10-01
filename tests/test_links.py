import csv
import io
import json
import zipfile
from datetime import date, timedelta

from tests.conftest import register


def create(client, url="https://example.com/long/page", slug="", expires_on=""):
    return client.post("/dashboard/links", data={
        "original_url": url, "slug": slug, "expires_on": expires_on})


def test_create_and_redirect(alice):
    create(alice, slug="portfolio")
    r = alice.get("/alice/portfolio")
    assert r.status_code == 302 and r.headers["location"] == "https://example.com/long/page"


def test_random_slug_is_generated(alice):
    create(alice)
    assert "alice/" in alice.get("/dashboard").text


def test_namespaces_do_not_collide(alice, make_client):
    bob = make_client()
    register(bob, "bob")
    create(alice, "https://alice.example.com", slug="portfolio")
    create(bob, "https://bob.example.com", slug="portfolio")
    assert alice.get("/alice/portfolio").headers["location"] == "https://alice.example.com"
    assert bob.get("/bob/portfolio").headers["location"] == "https://bob.example.com"


def test_duplicate_alias_for_same_user_rejected(alice):
    create(alice, slug="dup")
    r = create(alice, "https://other.example.com", slug="dup")
    assert r.status_code == 303
    assert "already have a link" in alice.get("/dashboard").text


def test_bad_urls_rejected(alice):
    for bad in ("javascript:alert(1)", "http://127.0.0.1", "http://testserver/x"):
        create(alice, bad, slug="bad")
    assert alice.get("/alice/bad").status_code == 404


def test_unknown_link_404(client):
    assert client.get("/nobody/nothing").status_code == 404


def test_expired_link_returns_410(alice, app):
    from app.models import Link, utcnow
    create(alice, slug="soon", expires_on=(date.today() + timedelta(days=2)).isoformat())
    with app.state.session_factory() as db:
        link = db.query(Link).filter_by(slug="soon").one()
        link.expires_at = utcnow() - timedelta(hours=1)
        db.commit()
    assert alice.get("/alice/soon").status_code == 410


def test_past_expiry_date_rejected(alice):
    create(alice, slug="past", expires_on=(date.today() - timedelta(days=1)).isoformat())
    assert alice.get("/alice/past").status_code == 404


def test_click_analytics(alice):
    create(alice, slug="stats")
    alice.get("/alice/stats", headers={"user-agent": "iPhone Mobile", "referer": "https://twitter.com/x"})
    alice.get("/alice/stats", headers={"user-agent": "Windows"})
    page = alice.get("/dashboard/links/1")
    assert page.status_code == 200
    assert "mobile" in page.text and "twitter.com" in page.text and "Direct" in page.text
    assert "2 total clicks" in page.text


def test_redirect_uses_cache(alice, redis_fake, app):
    from app.models import Link
    create(alice, slug="cached")
    alice.get("/alice/cached")  # miss -> fills cache
    assert json.loads(redis_fake.get("link:alice:cached"))["url"] == "https://example.com/long/page"
    with app.state.session_factory() as db:  # change DB behind the cache's back
        db.query(Link).filter_by(slug="cached").one().original_url = "https://changed.example.com"
        db.commit()
    assert alice.get("/alice/cached").headers["location"] == "https://example.com/long/page"


def test_delete_clears_cache(alice, redis_fake):
    create(alice, slug="gone")
    alice.get("/alice/gone")
    assert redis_fake.get("link:alice:gone")
    alice.post("/dashboard/links/bulk-delete", data={"ids": [1]})
    assert redis_fake.get("link:alice:gone") is None
    assert alice.get("/alice/gone").status_code == 404


def test_bulk_delete_only_own_links(alice, make_client):
    bob = make_client()
    register(bob, "bob")
    create(alice, slug="aaa1")
    create(alice, "https://example.org", slug="aaa2")
    create(bob, "https://bob.example.com", slug="bob1")
    bob_link_id = 3
    alice.post("/dashboard/links/bulk-delete", data={"ids": [1, 2, bob_link_id]})
    assert alice.get("/alice/aaa1").status_code == 404
    assert alice.get("/alice/aaa2").status_code == 404
    assert bob.get("/bob/bob1").status_code == 302  # untouched


def test_cannot_view_other_users_stats(alice, make_client):
    bob = make_client()
    register(bob, "bob")
    create(bob, "https://bob.example.com", slug="bob1")
    assert alice.get("/dashboard/links/1").status_code == 404
    assert alice.get("/dashboard/links/1/qr.png").status_code == 404


def test_csv_export(alice):
    create(alice, slug="one")
    create(alice, "https://example.org/two", slug="two")
    r = alice.get("/dashboard/links/export.csv")
    assert r.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert {row["slug"] for row in rows} == {"one", "two"}
    assert rows[0]["short_url"].startswith("http://testserver/alice/")


def test_qr_png_and_zip(alice):
    create(alice, slug="qr1")
    create(alice, "https://example.org", slug="qr2")
    png = alice.get("/dashboard/links/1/qr.png")
    assert png.content.startswith(b"\x89PNG")
    z = alice.get("/dashboard/links/qr.zip")
    names = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert sorted(names) == ["qr1.png", "qr2.png"]
    z = alice.get("/dashboard/links/qr.zip?ids=1")
    assert zipfile.ZipFile(io.BytesIO(z.content)).namelist() == ["qr1.png"]


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
