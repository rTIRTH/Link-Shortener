"""Import links from a CSV file."""

import csv
import io
import re
from datetime import datetime, timedelta, timezone

import pytest

from app import features
from app.config import settings
from app.importer import (
    MAX_IMPORT_BYTES,
    MAX_IMPORT_ROWS,
    TEMPLATE_ROWS,
    read_rows,
)
from app.models import Link
from app.utils import csv_safe, csv_safe_undo

PW = "password123"
FUTURE = (datetime.now(timezone.utc) + timedelta(days=90)).strftime("%Y-%m-%d")
PAST = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
HEADER = "original_url,slug,starts_at,expires_at,click_limit,tags,active\n"


def upload(client, data, name="links.csv"):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return client.post("/dashboard/links/import", files={"file": (name, data, "text/csv")})


def links(app, username="alice"):
    with app.state.session_factory() as db:
        return {
            link.slug: link for link in db.query(Link).all()
            if link.owner.username == username
        } and {
            link.slug: (link.original_url, link.click_limit, link.is_active,
                        [t.name for t in link.tags], link.expires_at is not None,
                        link.password_hash)
            for link in db.query(Link).all() if link.owner.username == username
        }


def message(page):
    """The summary line and the skipped rows' reasons, as plain text."""
    flat = re.sub(r"<[^>]+>", " ", page)
    return re.sub(r"\s+", " ", flat)


def skipped(page):
    return re.findall(
        r'<tr><td class="num">(\d+)</td><td class="mono clip">([^<]*)</td><td>([^<]*)</td></tr>',
        page)


# ---- the happy path ----------------------------------------------------------------------


def test_links_are_imported(alice, app):
    r = upload(alice, "original_url\nhttps://example.com/a\nhttps://example.com/b\n")
    assert r.status_code == 200 and "Imported 2 links." in message(r.text)
    assert len(links(app)) == 2
    assert {v[0] for v in links(app).values()} == {"https://example.com/a", "https://example.com/b"}


def test_one_link_reads_in_the_singular(alice):
    assert "Imported 1 link." in message(upload(alice, "original_url\nhttps://example.com/a").text)


def test_every_optional_column_is_read(alice, app):
    upload(alice, HEADER
           + f"https://example.com/a,summer,,{FUTURE},5,\"Work, Social\",yes\n"
           + "https://example.com/b,off-link,,,,,no\n")
    data = links(app)
    assert data["summer"][:5] == ("https://example.com/a", 5, True, ["social", "work"], True)
    assert data["off-link"][:5] == ("https://example.com/b", None, False, [], False)


def test_links_without_a_name_get_a_random_one(alice, app):
    upload(alice, "original_url\nhttps://example.com/a\nhttps://example.com/b\n")
    slugs = list(links(app))
    assert len(slugs) == 2 and all(re.fullmatch(r"[A-Za-z0-9_-]{3,}", s) for s in slugs)


def test_a_file_can_be_written_in_many_ways(alice, app):
    text = "\ufeffURL , Slug\r\nhttps://example.com/a , one\r\n\r\nhttps://example.com/b,two,extra,cells\r\n"
    upload(alice, text)  # BOM, other header names and case, Windows line endings, a blank line
    assert set(links(app)) == {"one", "two"}


def test_a_short_row_still_works(alice, app):
    upload(alice, "original_url,slug,tags\nhttps://example.com/a\n")
    assert len(links(app)) == 1


def test_passwords_are_never_imported(alice, app):
    upload(alice, "original_url,slug,password\nhttps://example.com/a,one,hunter22\n")
    assert links(app)["one"][5] is None


def test_the_sample_file_imports_cleanly(alice, app):
    sample = alice.get("/dashboard/links/import-template.csv")
    assert sample.status_code == 200 and "attachment" in sample.headers["content-disposition"]
    assert [r for r in csv.reader(io.StringIO(sample.text))] == TEMPLATE_ROWS
    r = upload(alice, sample.text)
    assert "Imported 2 links." in message(r.text) and "skipped" not in message(r.text)
    assert links(app)["summer"][3] == ["social", "work"]


def test_what_export_writes_import_can_read(alice, make_client, app):
    alice.post("/dashboard/links", data={
        "original_url": "https://example.com/a", "slug": "one", "tags": "work, fun",
        "click_limit": "7"})
    alice.post("/dashboard/links", data={"original_url": "https://example.com/b", "slug": "two"})
    exported = alice.get("/dashboard/links/export.csv").text
    bob = make_client()
    bob.post("/register", data={"username": "bob", "email": "bob@example.com", "password": PW})
    r = upload(bob, exported)
    assert "Imported 2 links." in message(r.text)
    assert links(app, "bob")["one"][:4] == ("https://example.com/a", 7, True, ["fun", "work"])
    assert links(app, "bob")["two"][0] == "https://example.com/b"


def test_other_peoples_names_do_not_get_in_the_way(alice, make_client, app):
    alice.post("/dashboard/links", data={"original_url": "https://example.com/a", "slug": "shared"})
    bob = make_client()
    bob.post("/register", data={"username": "bob", "email": "bob@example.com", "password": PW})
    assert "Imported 1 link." in message(
        upload(bob, "original_url,slug\nhttps://example.com/b,shared\n").text)


def test_formula_guards_from_export_are_removed():
    assert csv_safe_undo(csv_safe("=1+1")) == "=1+1"
    assert csv_safe_undo(csv_safe("-x")) == "-x"
    assert csv_safe_undo("'quoted") == "'quoted" and csv_safe_undo("") == ""


# ---- rows that cannot be imported ------------------------------------------------------


def test_bad_rows_are_skipped_with_a_reason_and_the_rest_still_import(alice, app):
    r = upload(alice, HEADER
               + "https://example.com/ok,fine,,,,,\n"                      # 2: good
               + "not a url,,,,,,\n"                                      # 3: spaces
               + "http://127.0.0.1/admin,,,,,,\n"                         # 4: private
               + "https://example.com/c,fine,,,,,\n"                      # 5: same name again
               + "https://example.com/d,d d,,,,,\n"                       # 6: bad name
               + "https://example.com/e,,,,zero,,\n"                      # 7: bad limit
               + "https://example.com/f,,notadate,,,,\n"                  # 8: bad date
               + f"https://example.com/g,,{FUTURE},{PAST},,,\n"          # 9: ends before start
               + f"https://example.com/h,,,{PAST},,,\n"                   # 10: already over
               + "https://example.com/i,,,,,a;b/c,\n"                     # 11: bad tag
               + "https://example.com/j,,,,,\"1,2,3,4,5,6\",\n"           # 12: six tags
               + "https://example.com/k,good,,,,,\n")                     # 13: good
    page = r.text
    assert "Imported 2 links." in message(page) and "10 rows were skipped." in message(page)
    rows = skipped(page)
    assert [int(x[0]) for x in rows] == [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    reasons = {int(n): why for n, _url, why in rows}
    assert "spaces" in reasons[3] and "Private" in reasons[4]
    assert "already have a link called &#39;fine&#39;" in reasons[5]
    assert "whole number" in reasons[7] and "not valid" in reasons[8]
    assert "after the start" in reasons[9] or "not valid" in reasons[9]
    assert "future" in reasons[10] and "5 tags" in reasons[12]
    assert set(links(app)) == {"fine", "good"}


def test_an_address_already_taken_by_an_existing_link_is_skipped(alice, app):
    alice.post("/dashboard/links", data={"original_url": "https://example.com/a", "slug": "mine"})
    r = upload(alice, "original_url,slug\nhttps://example.com/b,mine\n")
    assert "0 links" in message(r.text) or "Imported 0" in message(r.text)
    assert links(app)["mine"][0] == "https://example.com/a"  # untouched


def test_unsafe_addresses_are_skipped(alice, app, monkeypatch):
    monkeypatch.setattr(settings, "blocked_domains", ("phish.test",))
    r = upload(alice, "original_url\nhttps://www.phish.test/x\nhttps://example.com/ok\n")
    assert "Imported 1 link." in message(r.text)
    assert "unsafe sites" in skipped(r.text)[0][2]
    assert len(links(app)) == 1


def test_more_than_fifty_tags_stop_only_the_rows_that_would_pass_the_limit(alice, app):
    rows = ["original_url,tags"]
    for i in range(11):  # 11 rows x 5 new tags = 55 tags
        rows.append(f"https://example.com/{i},\"" + ",".join(f"t{i}x{j}" for j in range(5)) + '"')
    r = upload(alice, "\n".join(rows))
    assert "Imported 10 links." in message(r.text) and "up to 50 tags" in skipped(r.text)[0][2]


def test_the_page_lists_only_the_first_twenty_skipped_rows(alice):
    body = "original_url\n" + "\n".join(f"bad address {i}" for i in range(25))
    r = upload(alice, body)
    assert len(skipped(r.text)) == 20 and "25 rows were skipped." in message(r.text)
    assert "Only the first 20 skipped rows are shown." in r.text


def test_long_addresses_are_shortened_in_the_list(alice):
    r = upload(alice, "original_url\nbad " + "x" * 300)
    assert len(skipped(r.text)[0][1]) <= 80


# ---- a bad file ------------------------------------------------------------------------


@pytest.mark.parametrize("data, reason", [
    ("", "must hold the column names"),
    ("slug,tags\nabc,work\n", "must hold the column names"),
    ("original_url\n", "no links in it"),
    ("original_url\n\n,\n", "no links in it"),
    (b"original_url\n\xff\xfe\xfa\n", "UTF-8"),
])
def test_a_bad_file_is_explained(alice, app, data, reason):
    r = upload(alice, data)
    assert r.status_code == 400 and reason in r.text and not links(app)


def test_the_size_and_row_limits(alice, app):
    ok = "original_url\n" + "\n".join(f"https://example.com/{i}" for i in range(MAX_IMPORT_ROWS))
    assert "Imported 200 links." in message(upload(alice, ok).text)
    too_many = ok + "\nhttps://example.com/one-more"
    assert "up to 200 links" in upload(alice, too_many).text
    big = "original_url\n" + "https://example.com/" + "x" * MAX_IMPORT_BYTES
    assert "too big" in upload(alice, big).text
    assert len(links(app)) == 200


def test_posting_without_a_file_asks_for_one(alice):
    r = alice.post("/dashboard/links/import")
    assert r.status_code == 400 and "Choose a CSV file first." in r.text


def test_read_rows_numbers_lines_like_a_spreadsheet():
    rows = read_rows(b"original_url\nhttps://a.test\n\nhttps://b.test\n")
    assert [n for n, _ in rows] == [2, 4]  # the blank line 3 is skipped but still counted


# ---- access ---------------------------------------------------------------------------


def test_the_pages_need_a_login(client):
    for path in ("/dashboard/links/import", "/dashboard/links/import-template.csv"):
        assert client.get(path, follow_redirects=False).status_code in (303, 307)
    assert client.post("/dashboard/links/import", follow_redirects=False).status_code in (303, 307)


def test_the_form_page_and_the_entry_link(alice):
    page = alice.get("/dashboard/links/import").text
    assert 'enctype="multipart/form-data"' in page and 'name="file"' in page
    assert "original_url" in page and "Passwords are never imported" in page
    assert 'href="/dashboard/links/import"' in alice.get("/dashboard").text


def test_importing_too_often_is_slowed_down(alice, redis_fake):
    for _ in range(5):
        assert upload(alice, "original_url\nbad address").status_code == 200
    r = upload(alice, "original_url\nbad address")
    assert r.status_code == 429 and "too quickly" in r.text


def test_a_locked_import_is_refused(alice, app, monkeypatch):
    monkeypatch.setattr(features, "PAID", frozenset({"csv_import"}))
    page = alice.get("/dashboard/links/import").text
    assert "paid plan" in page and 'name="file"' not in page
    r = upload(alice, "original_url\nhttps://example.com/a\n")
    assert r.status_code == 403 and not links(app)
    assert "paid plan" in alice.get("/dashboard").text


def test_locked_click_limits_and_tags_cannot_sneak_in_through_a_file(alice, app, monkeypatch):
    monkeypatch.setattr(features, "PAID", frozenset({"click_limit", "tags"}))
    r = upload(alice, "original_url,slug,click_limit,tags\n"
                      "https://example.com/a,one,5,\nhttps://example.com/b,two,,work\n"
                      "https://example.com/c,three,,\n")
    assert "Imported 1 link." in message(r.text)
    assert set(links(app)) == {"three"} and len(skipped(r.text)) == 2


@pytest.mark.parametrize("lang, word, reason", [
    ("hi", "आयात", "असुरक्षित"), ("gu", "આયાત", "અસુરક્ષિત"),
])
def test_the_import_screens_render_in_every_language(alice, monkeypatch, lang, word, reason):
    monkeypatch.setattr(settings, "blocked_domains", ("phish.test",))
    alice.post("/language", data={"lang": lang, "next": "/"})
    assert word in alice.get("/dashboard/links/import").text
    page = upload(alice, "original_url\nhttps://phish.test/x\nhttps://example.com/ok\n").text
    assert word in page and reason in page and "Imported" not in page
