"""Changing where a link goes is written in the activity log (old address -> new address)."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.activity import link_events
from app.models import Link, LinkEdit

OLD = "https://example.com/old"
NEW = "https://example.com/new"


def make(client, slug="lnk", url=OLD):
    return client.post("/dashboard/links", data={"original_url": url, "slug": slug})


def lid(app, slug="lnk"):
    with app.state.session_factory() as db:
        return db.query(Link).filter_by(slug=slug).one().id


def edit(client, link_id, url, **extra):
    data = {"original_url": url, "password_action": "keep", **extra}
    return client.post(f"/dashboard/links/{link_id}/edit", data=data)


def edits(app, slug="lnk"):
    with app.state.session_factory() as db:
        link = db.query(Link).filter_by(slug=slug).one()
        return [(e.old_url, e.new_url) for e in link.edits]


def log(client, link_id):
    page = client.get(f"/dashboard/links/{link_id}").text
    start = page.index("<ul class=\"plain\">")
    return page[start:page.index("</ul>", start)]


def test_a_new_destination_is_remembered(alice, app):
    make(alice)
    edit(alice, lid(app), NEW)
    assert edits(app) == [(OLD, NEW)]
    edit(alice, lid(app), "https://example.com/third")
    assert edits(app) == [(OLD, NEW), (NEW, "https://example.com/third")]


def test_saving_without_changing_the_address_adds_nothing(alice, app):
    make(alice)
    edit(alice, lid(app), OLD)
    edit(alice, lid(app), OLD, click_limit="3", limit_box="1")  # other settings changed
    assert edits(app) == []


def test_a_refused_edit_leaves_no_history(alice, app):
    make(alice)
    edit(alice, lid(app), "not a url with spaces")
    edit(alice, lid(app), "http://127.0.0.1/admin")
    assert edits(app) == []


def test_the_activity_log_shows_old_and_new(alice, app):
    make(alice)
    assert "Destination changed" not in log(alice, lid(app))
    edit(alice, lid(app), NEW)
    entry = log(alice, lid(app))
    assert "Destination changed" in entry
    assert f"<s>{OLD}</s> → {NEW}" in entry
    assert entry.index("Created") < entry.index("Destination changed")  # oldest first


def test_addresses_in_the_log_cannot_inject_html(alice, app):
    make(alice)
    edit(alice, lid(app), 'https://example.com/a?x=<script>alert(1)</script>')
    entry = log(alice, lid(app))
    assert "<script>alert" not in entry and "&lt;script&gt;" in entry


def test_the_edit_page_says_changes_are_logged(alice, app):
    make(alice)
    page = alice.get(f"/dashboard/links/{lid(app)}/edit").text
    assert "Every change to the destination is written in the activity log." in page


def test_history_is_kept_per_link_and_private(alice, make_client, app):
    make(alice, "one")
    make(alice, "two")
    edit(alice, lid(app, "one"), NEW)
    assert edits(app, "two") == []
    bob = make_client()
    bob.post("/register", data={"username": "bob", "email": "bob@example.com",
                                "password": "password123"})
    assert bob.get(f"/dashboard/links/{lid(app, 'one')}").status_code == 404


def test_deleting_a_link_deletes_its_history(alice, app):
    make(alice)
    edit(alice, lid(app), NEW)
    alice.post(f"/dashboard/links/{lid(app)}/delete")
    with app.state.session_factory() as db:
        assert db.query(LinkEdit).count() == 0


def test_only_the_ten_latest_changes_are_listed():
    now = datetime(2026, 11, 15, tzinfo=timezone.utc)
    link = SimpleNamespace(created_at=now - timedelta(days=30), starts_at=None, expires_at=None)
    changes = [SimpleNamespace(at=now - timedelta(days=20 - i), old_url=f"o{i}", new_url=f"n{i}")
               for i in range(14)]
    shown = [e for e in link_events(link, now, (), None, changes) if e["key"] == "dest"]
    assert len(shown) == 10 and shown[0]["old"] == "o4" and shown[-1]["new"] == "n13"
    assert link_events(link, now) == link_events(link, now, (), None, ())


def test_the_log_renders_in_every_language(alice, app):
    make(alice)
    edit(alice, lid(app), NEW)
    for lang, word in (("hi", "गंतव्य बदला गया"), ("gu", "ગંતવ્ય બદલાયું")):
        alice.post("/language", data={"lang": lang, "next": "/"})
        assert word in log(alice, lid(app))
        edit_page = alice.get(f"/dashboard/links/{lid(app)}/edit").text
        assert "Every change" not in edit_page
