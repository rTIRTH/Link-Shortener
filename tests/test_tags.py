"""Tags: group links, filter the dashboard by a tag, compare a whole tag in one graph."""

import csv
import io
import re

import pytest

from app.models import Link, Tag, User, link_tags
from app.tags import (
    MAX_TAGS_PER_USER,
    clean_tag,
    parse_tags,
    prune_tags,
    set_link_tags,
    tag_color,
)

PW = "password123"


def make(client, slug="lnk", **extra):
    return client.post("/dashboard/links", data={
        "original_url": "https://example.com/" + slug, "slug": slug, **extra})


def tags_of(app, slug):
    with app.state.session_factory() as db:
        return [t.name for t in db.query(Link).filter_by(slug=slug).one().tags]


def all_tags(app):
    with app.state.session_factory() as db:
        return sorted(t.name for t in db.query(Tag))


def link_id(app, slug):
    with app.state.session_factory() as db:
        return db.query(Link).filter_by(slug=slug).one().id


def edit(client, lid, **fields):
    data = {"original_url": "https://example.com/x", "password_action": "keep", **fields}
    if "tags" in fields:
        data["tags_box"] = "1"  # the edit page sends this along with its tags box
    return client.post(f"/dashboard/links/{lid}/edit", data=data)


def rows(page):
    """The short links listed in the table, in order."""
    return re.findall(r'class="mono" href="[^"]*/alice/([^"]+)"', page)


# ---- reading tags -----------------------------------------------------------------------


def test_tags_are_cleaned_and_deduplicated():
    assert parse_tags("Work, school ,WORK,  my  tag ,,") == ["work", "school", "my tag"]
    assert parse_tags("a\nb") == ["a", "b"]
    assert parse_tags("") == parse_tags(None) == []
    assert clean_tag("  Big   Idea ") == "big idea"


def test_tags_in_hindi_and_gujarati_work():
    assert parse_tags("काम, स्कूल") == ["काम", "स्कूल"]
    assert parse_tags("કામ") == ["કામ"]


@pytest.mark.parametrize("bad", ["a#b", "a/b", "a?b", "a&b", 'a"b', "a<b", "x" * 25])
def test_unsafe_or_long_tags_are_refused(bad):
    with pytest.raises(ValueError, match="up to 24 characters"):
        parse_tags(bad)


def test_a_link_can_have_five_tags_not_six():
    assert len(parse_tags("a,b,c,d,e")) == 5
    with pytest.raises(ValueError, match="up to 5 tags"):
        parse_tags("a,b,c,d,e,f")


def test_a_tag_always_wears_the_same_colour():
    assert tag_color("work") == tag_color("work")
    assert {tag_color(n) for n in ("work", "school", "home", "fun", "x", "y", "z", "w")} <= set(
        range(1, 7))
    assert len({tag_color(f"tag{i}") for i in range(40)}) > 3  # they do vary


# ---- creating and editing -----------------------------------------------------------------


def test_tags_are_added_when_a_link_is_created(alice, app):
    make(alice, tags="Work, school")
    assert tags_of(app, "lnk") == ["school", "work"]
    assert all_tags(app) == ["school", "work"]


def test_two_links_share_one_tag(alice, app):
    make(alice, "one", tags="work")
    make(alice, "two", tags="WORK")
    assert all_tags(app) == ["work"]  # one tag, not two
    assert tags_of(app, "one") == tags_of(app, "two") == ["work"]


def test_bad_tags_create_nothing(alice, app):
    make(alice, tags="a,b,c,d,e,f")
    assert "up to 5 tags" in alice.get("/dashboard").text
    make(alice, "two", tags="no/slash")
    with app.state.session_factory() as db:
        assert db.query(Link).count() == 0 and db.query(Tag).count() == 0


def test_the_edit_page_changes_tags(alice, app):
    make(alice, tags="work, fun")
    lid = link_id(app, "lnk")
    page = alice.get(f"/dashboard/links/{lid}/edit").text
    assert 'name="tags"' in page and 'value="fun, work"' in page
    edit(alice, lid, tags="work, school")
    assert tags_of(app, "lnk") == ["school", "work"]
    assert all_tags(app) == ["school", "work"]  # "fun" is on no link now, so it is forgotten


def test_clearing_the_box_removes_every_tag(alice, app):
    make(alice, tags="work")
    edit(alice, link_id(app, "lnk"), tags="")
    assert tags_of(app, "lnk") == [] and all_tags(app) == []


def test_a_form_without_the_tags_box_leaves_tags_alone(alice, app):
    make(alice, tags="work")
    edit(alice, link_id(app, "lnk"))
    assert tags_of(app, "lnk") == ["work"]


def test_a_tag_stays_while_another_link_uses_it(alice, app):
    make(alice, "one", tags="work")
    make(alice, "two", tags="work")
    edit(alice, link_id(app, "one"), tags="")
    assert all_tags(app) == ["work"] and tags_of(app, "two") == ["work"]


def test_deleting_links_forgets_tags_nothing_uses(alice, app):
    make(alice, "one", tags="work, solo")
    make(alice, "two", tags="work")
    alice.post(f"/dashboard/links/{link_id(app, 'one')}/delete")
    assert all_tags(app) == ["work"]
    alice.post("/dashboard/links/bulk-delete", data={"ids": [link_id(app, "two")]})
    assert all_tags(app) == []
    with app.state.session_factory() as db:
        assert db.execute(link_tags.select()).all() == []


def test_the_fifty_tag_limit(app):
    with app.state.session_factory() as db:
        user = User(username="bulk", email="b@example.com", password_hash="x")
        db.add(user)
        db.flush()
        link = Link(user_id=user.id, slug="abc", original_url="https://example.com")
        db.add(link)
        names = [f"t{i}" for i in range(MAX_TAGS_PER_USER)]
        for start in range(0, len(names), 5):
            set_link_tags(db, user, link, names[start:start + 5])
            db.flush()
        with pytest.raises(ValueError, match="up to 50 tags"):
            set_link_tags(db, user, link, ["one-too-many"])
        db.rollback()


def test_prune_only_touches_the_users_own_tags(alice, make_client, app):
    bob = make_client()
    bob.post("/register", data={"username": "bob", "email": "bob@example.com", "password": PW})
    make(alice, tags="work")
    with app.state.session_factory() as db:
        mine = db.query(User).filter_by(username="alice").one()
        db.add(Tag(user_id=mine.id, name="unused"))
        db.flush()
        bobs = db.query(User).filter_by(username="bob").one()
        db.add(Tag(user_id=bobs.id, name="bobs-unused"))
        db.flush()
        prune_tags(db, mine)
        db.commit()
    assert all_tags(app) == ["bobs-unused", "work"]


# ---- the dashboard -----------------------------------------------------------------------


def test_the_dashboard_shows_tag_chips_and_a_filter_bar(alice, app):
    make(alice, "one", tags="work, fun")
    make(alice, "two", tags="work")
    make(alice, "three")
    page = alice.get("/dashboard").text
    bar = page[page.index('class="tagbar"'):page.index("</nav>", page.index('class="tagbar"'))]
    assert 'href="/dashboard?tag=work"' in bar and "work <b>2</b>" in bar and "fun <b>1</b>" in bar
    assert 'class="chip all on"' in bar
    assert f'class="chip s{tag_color("work")}"' in page  # the chip in the row, in its colour


def test_filtering_by_a_tag(alice, app):
    make(alice, "one", tags="work")
    make(alice, "two", tags="fun")
    make(alice, "three", tags="work, fun")
    make(alice, "four")
    assert sorted(rows(alice.get("/dashboard?tag=work").text)) == ["one", "three"]
    assert sorted(rows(alice.get("/dashboard?tag=FUN").text)) == ["three", "two"]
    assert len(rows(alice.get("/dashboard").text)) == 4
    page = alice.get("/dashboard?tag=work").text
    assert 'class="chip s' in page and " on" in page and "Compare this tag" in page
    assert "Compare this tag" not in alice.get("/dashboard").text


def test_an_unknown_tag_shows_a_friendly_empty_page(alice):
    make(alice, "one", tags="work")
    page = alice.get("/dashboard?tag=nothing").text
    assert "No links with this tag" in page and "Compare this tag" in page


def test_tags_are_private_to_their_owner(alice, make_client):
    make(alice, "mine", tags="secret")
    bob = make_client()
    bob.post("/register", data={"username": "bob", "email": "bob@example.com", "password": PW})
    bob.post("/dashboard/links", data={"original_url": "https://example.org/b", "slug": "bobs"})
    page = bob.get("/dashboard?tag=secret").text
    assert "mine" not in page and "secret" not in bob.get("/dashboard").text
    assert bob.get("/dashboard/links/compare?tag=secret").status_code == 303  # nothing of his


def test_tags_with_non_latin_names_filter_correctly(alice):
    make(alice, "one", tags="काम")
    make(alice, "two")
    assert rows(alice.get("/dashboard?tag=काम").text) == ["one"]
    assert "काम" in alice.get("/dashboard").text


def test_the_tags_show_on_the_analytics_page(alice, app):
    make(alice, tags="work")
    page = alice.get(f"/dashboard/links/{link_id(app, 'lnk')}").text
    assert 'href="/dashboard?tag=work"' in page


def test_the_create_form_offers_existing_tags_as_chips(alice):
    assert "data-tag-pick" not in alice.get("/dashboard").text  # none yet
    make(alice, tags="work")
    page = alice.get("/dashboard").text
    assert 'data-tag-pick="work" data-target="tags-create"' in page
    assert "/static/tags.js" in page


def test_the_edit_page_marks_the_links_own_tags(alice, app):
    make(alice, "one", tags="work")
    make(alice, "two", tags="fun")
    page = alice.get(f"/dashboard/links/{link_id(app, 'one')}/edit").text
    assert re.search(r'class="chip s\d on" data-tag-pick="work"[^>]*aria-pressed="true"', page)
    assert re.search(r'class="chip s\d" data-tag-pick="fun"[^>]*aria-pressed="false"', page)
    assert "/static/tags.js" in page


def test_the_chip_script_is_served(alice):
    js = alice.get("/static/tags.js")
    assert js.status_code == 200 and "data-tag-pick" in js.text


# ---- compare a whole tag in one graph ------------------------------------------------------


def test_a_tag_is_compared_in_one_graph(alice):
    make(alice, "one", tags="work")
    make(alice, "two", tags="work")
    make(alice, "three", tags="fun")
    alice.get("/alice/one")
    page = alice.get("/dashboard/links/compare?tag=work").text
    listed = re.findall(r'/dashboard/links/\d+">([^<]*)<', page)  # the table of compared links
    assert sorted(x.split("/")[-1] for x in listed) == ["one", "two"]
    assert 'class="chip s' in page and "work</span>" in page
    assert "Showing the" not in page


def test_a_tag_of_one_link_goes_to_that_links_page(alice, app):
    make(alice, "one", tags="solo")
    r = alice.get("/dashboard/links/compare?tag=solo")
    assert r.status_code == 303
    assert r.headers["location"] == f"/dashboard/links/{link_id(app, 'one')}"


def test_comparing_an_unknown_tag_goes_back_with_a_message(alice):
    r = alice.get("/dashboard/links/compare?tag=nope")
    assert r.status_code == 303 and r.headers["location"] == "/dashboard"
    assert "No links have that tag." in alice.get("/dashboard").text


def test_a_big_tag_shows_its_most_clicked_links(alice):
    for i in range(10):
        make(alice, f"l{i:02d}", tags="big")
    for _ in range(3):
        alice.get("/alice/l09")  # the busiest
    page = alice.get("/dashboard/links/compare?tag=big").text
    shown = set(re.findall(r'/dashboard/links/\d+">[^<]*?/alice/(l\d\d)<', page))
    assert len(shown) == 8 and "l09" in shown
    assert "Showing the 8 most-clicked links of this tag." in page


def test_the_old_way_of_comparing_still_works(alice, app):
    make(alice, "one")
    make(alice, "two")
    ids = [link_id(app, "one"), link_id(app, "two")]
    page = alice.get("/dashboard/links/compare", params={"ids": ids}).text
    listed = re.findall(r'/dashboard/links/\d+">([^<]*)<', page)
    assert sorted(x.split("/")[-1] for x in listed) == ["one", "two"] and 'class="chip' not in page


# ---- other places ---------------------------------------------------------------------


def test_the_csv_has_the_new_columns(alice):
    make(alice, "one", tags="work, fun", click_limit="5")
    rows_ = list(csv.DictReader(io.StringIO(alice.get("/dashboard/links/export.csv").text)))
    assert rows_[0]["tags"] == "fun, work" and rows_[0]["click_limit"] == "5"
    assert rows_[0]["archived"] == "no"


def test_deleting_an_account_removes_its_tags(alice, app):
    make(alice, tags="work")
    r = alice.post("/account/delete", data={"confirm": "alice", "password": PW})
    assert r.status_code == 303
    assert all_tags(app) == []
    with app.state.session_factory() as db:
        assert db.execute(link_tags.select()).all() == []


@pytest.mark.parametrize("lang, word", [("hi", "टैग"), ("gu", "ટૅગ")])
def test_the_tag_screens_render_in_every_language(alice, app, lang, word):
    make(alice, "one", tags="work")
    make(alice, "two", tags="work")
    alice.post("/language", data={"lang": lang, "next": "/"})
    assert word in alice.get("/dashboard").text
    assert word in alice.get(f"/dashboard/links/{link_id(app, 'one')}/edit").text
    assert "Compare this tag" not in alice.get("/dashboard?tag=work").text
