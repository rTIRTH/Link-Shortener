"""Archive: hide links from the dashboard list without deleting them or their stats."""

import io
import re
import zipfile

from app.models import Click, Link

PW = "password123"


def make(client, slug="lnk", **extra):
    return client.post("/dashboard/links", data={
        "original_url": "https://example.com/" + slug, "slug": slug, **extra})


def lid(app, slug):
    with app.state.session_factory() as db:
        return db.query(Link).filter_by(slug=slug).one().id


def archived(app, slug):
    with app.state.session_factory() as db:
        return db.query(Link).filter_by(slug=slug).one().archived_at is not None


def rows(page):
    return re.findall(r'class="mono" href="[^"]*/alice/([^"]+)"', page)


def archive(client, app, *slugs, action="archive"):
    return client.post("/dashboard/links/archive",
                       data={"ids": [lid(app, s) for s in slugs], "action": action})


def test_archived_links_leave_the_list_and_come_back(alice, app):
    make(alice, "one")
    make(alice, "two")
    r = archive(alice, app, "one")
    assert r.status_code == 303 and archived(app, "one") and not archived(app, "two")
    assert rows(alice.get("/dashboard").text) == ["two"]
    assert rows(alice.get("/dashboard?view=archived").text) == ["one"]
    archive(alice, app, "one", action="restore")
    assert not archived(app, "one")
    assert sorted(rows(alice.get("/dashboard").text)) == ["one", "two"]


def test_an_archived_link_keeps_working_and_counting(alice, app):
    make(alice, "one")
    alice.get("/alice/one")
    archive(alice, app, "one")
    r = alice.get("/alice/one")
    assert r.status_code == 302 and r.headers["location"] == "https://example.com/one"
    with app.state.session_factory() as db:
        link = db.query(Link).filter_by(slug="one").one()
        assert link.click_count == 2 and db.query(Click).filter_by(link_id=link.id).count() == 2


def test_stats_of_an_archived_link_are_still_there(alice, app):
    make(alice, "one")
    alice.get("/alice/one")
    archive(alice, app, "one")
    page = alice.get(f"/dashboard/links/{lid(app, 'one')}")
    assert page.status_code == 200 and "1 total click" in page.text
    assert alice.get(f"/dashboard/links/{lid(app, 'one')}/edit").status_code == 200


def test_the_tabs_show_how_many_links_are_in_each(alice, app):
    make(alice, "one")
    make(alice, "two")
    make(alice, "three")
    archive(alice, app, "one")
    page = alice.get("/dashboard").text
    tabs = page[page.index('class="viewtabs"'):page.index("</nav>", page.index('class="viewtabs"'))]
    assert re.search(r'class="on"[^>]*>Active <b>2</b>', tabs)
    assert re.search(r'href="/dashboard\?view=archived"[^>]*>.*?Archived <b>1</b>', tabs, re.S)
    page = alice.get("/dashboard?view=archived").text
    assert re.search(r'class="on" aria-current="page">[^<]*<svg.*?Archived <b>1</b>', page, re.S)


def test_the_toolbar_offers_archive_or_restore(alice, app):
    make(alice, "one")
    page = alice.get("/dashboard").text
    assert 'name="action" value="archive"' in page and 'value="restore"' not in page
    archive(alice, app, "one")
    page = alice.get("/dashboard?view=archived").text
    assert 'name="action" value="restore"' in page and 'value="archive"' not in page


def test_an_empty_archive_explains_itself(alice, app):
    make(alice, "one")
    page = alice.get("/dashboard?view=archived").text
    assert "No archived links" in page and "still work" in page


def test_archiving_nothing_asks_for_a_selection(alice):
    r = alice.post("/dashboard/links/archive", data={"action": "archive"})
    assert r.status_code == 303
    assert "Select at least one link first." in alice.get("/dashboard").text


def test_the_messages_say_what_happened(alice, app):
    make(alice, "one")
    archive(alice, app, "one")
    assert "Archived 1 link(s). They are hidden from your list but still work." in (
        alice.get("/dashboard").text)
    archive(alice, app, "one", action="restore")
    assert "Restored 1 link(s)." in alice.get("/dashboard").text


def test_nobody_can_archive_someone_elses_link(alice, make_client, app):
    make(alice, "mine")
    bob = make_client()
    bob.post("/register", data={"username": "bob", "email": "bob@example.com", "password": PW})
    bob.post("/dashboard/links/archive", data={"ids": [lid(app, "mine")], "action": "archive"})
    assert not archived(app, "mine")
    assert bob.post(f"/dashboard/links/{lid(app, 'mine')}/archive",
                    data={"archived": "1"}).status_code == 404
    assert not archived(app, "mine")


def test_one_link_is_archived_from_its_edit_page(alice, app):
    make(alice, "one")
    page = alice.get(f"/dashboard/links/{lid(app, 'one')}/edit").text
    assert "Archive link" in page and "Restore link" not in page
    r = alice.post(f"/dashboard/links/{lid(app, 'one')}/archive", data={"archived": "1"})
    assert r.status_code == 303 and r.headers["location"].endswith("/edit")
    assert archived(app, "one")
    page = alice.get(f"/dashboard/links/{lid(app, 'one')}/edit").text
    assert "This link is archived." in page and "Restore link" in page
    alice.post(f"/dashboard/links/{lid(app, 'one')}/archive", data={"archived": "0"})
    assert not archived(app, "one")


def test_archiving_twice_or_with_nonsense_is_harmless(alice, app):
    make(alice, "one")
    url = f"/dashboard/links/{lid(app, 'one')}/archive"
    alice.post(url, data={"archived": "1"})
    alice.post(url, data={"archived": "1"})
    assert archived(app, "one")
    alice.post(url, data={"archived": "maybe"})
    assert archived(app, "one")


def test_qr_download_without_a_selection_skips_archived_links(alice, app):
    make(alice, "one")
    make(alice, "two")
    archive(alice, app, "one")
    z = alice.get("/dashboard/links/qr.zip")
    assert zipfile.ZipFile(io.BytesIO(z.content)).namelist() == ["two.png"]
    z = alice.get(f"/dashboard/links/qr.zip?ids={lid(app, 'one')}")  # but a pick always works
    assert zipfile.ZipFile(io.BytesIO(z.content)).namelist() == ["one.png"]


def test_tag_filters_follow_the_current_view(alice, app):
    make(alice, "one", tags="work")
    make(alice, "two", tags="work")
    archive(alice, app, "one")
    assert rows(alice.get("/dashboard?tag=work").text) == ["two"]
    assert rows(alice.get("/dashboard?view=archived&tag=work").text) == ["one"]
    page = alice.get("/dashboard?view=archived").text
    assert "work <b>1</b>" in page and "view=archived" in page


def test_archived_links_can_still_be_compared_and_deleted(alice, app):
    make(alice, "one", tags="g")
    make(alice, "two", tags="g")
    archive(alice, app, "one")
    listed = re.findall(r'/dashboard/links/\d+">([^<]*)<',
                        alice.get("/dashboard/links/compare?tag=g").text)
    assert len(listed) == 2  # a tag compares all its links, archived or not
    alice.post("/dashboard/links/bulk-delete", data={"ids": [lid(app, "one")]})
    with app.state.session_factory() as db:
        assert db.query(Link).filter_by(slug="one").count() == 0


def test_the_csv_says_which_links_are_archived(alice, app):
    make(alice, "one")
    archive(alice, app, "one")
    assert "one" in alice.get("/dashboard/links/export.csv").text
    assert ",yes," in alice.get("/dashboard/links/export.csv").text


def test_the_archive_screens_render_in_every_language(alice, app):
    make(alice, "one")
    archive(alice, app, "one")
    for lang, word in (("hi", "आर्काइव"), ("gu", "આર્કાઇવ")):
        alice.post("/language", data={"lang": lang, "next": "/"})
        assert word in alice.get("/dashboard?view=archived").text
        assert word in alice.get(f"/dashboard/links/{lid(app, 'one')}/edit").text
