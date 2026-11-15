"""Link check on create: refuse unsafe addresses, warn about ones that do not answer."""

import re
import socket
from html import unescape

import httpx
import pytest

from app import linkcheck
from app.config import Settings, settings
from app.linkcheck import check_destination, host_blocked, probe
from app.models import Link

UNSAFE = "This web address is on a list of unsafe sites, so it can't be shortened."
NO_ANSWER = "that address did not answer when we checked it"


@pytest.fixture()
def net(monkeypatch):
    """A pretend internet. net.routes maps 'host/path' to a status, (status, location) or error."""

    class Net:
        def __init__(self):
            self.routes: dict = {}
            self.calls: list[str] = []
            self.addresses: dict[str, str] = {}  # host -> the address its name points to
            self.dns_missing: set[str] = set()

    n = Net()

    def handler(request: httpx.Request) -> httpx.Response:
        key = request.url.host + request.url.path
        n.calls.append(key)
        what = n.routes.get(key, 200)
        if what == "refused":
            raise httpx.ConnectError("refused", request=request)
        if what == "slow":
            raise httpx.ReadTimeout("slow", request=request)
        if isinstance(what, tuple):
            return httpx.Response(what[0], headers={"location": what[1]})
        return httpx.Response(what)

    def resolve(host, *args, **kwargs):
        if host in n.dns_missing:
            raise socket.gaierror("no such name")
        address = n.addresses.get(host, "93.184.216.34")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))]

    monkeypatch.setattr(linkcheck, "_TRANSPORT", httpx.MockTransport(handler))
    monkeypatch.setattr(linkcheck.socket, "getaddrinfo", resolve)
    monkeypatch.setattr(settings, "link_check", True)
    return n


def verdict(url="https://example.com/page"):
    return check_destination(url).verdict


# ---- the blocklist ----------------------------------------------------------------------


@pytest.mark.parametrize("host, blocked", [
    ("bad.test", True), ("www.bad.test", True), ("a.b.bad.test", True), ("BAD.TEST", True),
    ("bad.test.", True), ("notbad.test", False), ("bad.test.example.com", False), ("", False),
])
def test_the_blocklist_matches_a_domain_and_its_subdomains(monkeypatch, host, blocked):
    monkeypatch.setattr(settings, "blocked_domains", ("bad.test",))
    assert host_blocked(host) is blocked


def test_the_blocklist_works_even_when_the_check_is_switched_off(monkeypatch):
    monkeypatch.setattr(settings, "blocked_domains", ("bad.test",))
    assert not settings.link_check
    assert check_destination("https://www.bad.test/x").verdict == "blocked"
    assert check_destination("https://fine.test/x").verdict == "skipped"


def test_the_settings_are_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("BLOCKED_DOMAINS", " Bad.com, .evil.test ,, ")
    monkeypatch.setenv("LINK_CHECK", "false")
    monkeypatch.setenv("SAFE_BROWSING_API_KEY", "k123")
    fresh = Settings()
    assert fresh.blocked_domains == ("bad.com", "evil.test")
    assert fresh.link_check is False and fresh.safe_browsing_key == "k123"
    monkeypatch.delenv("BLOCKED_DOMAINS")
    monkeypatch.delenv("LINK_CHECK")
    assert Settings().blocked_domains == () and Settings().link_check is True


# ---- does it answer? ------------------------------------------------------------------


def test_a_working_site_is_fine(net):
    assert verdict() == "ok" and net.calls == ["example.com/page"]


@pytest.mark.parametrize("status", [404, 410, 500, 502, 503])
def test_broken_pages_are_flagged(net, status):
    net.routes["example.com/page"] = status
    assert verdict() == "unreachable"


@pytest.mark.parametrize("status", [200, 204, 401, 403, 405, 429, 451])
def test_sites_that_merely_dislike_robots_are_not_held_against_them(net, status):
    net.routes["example.com/page"] = status
    assert verdict() == "ok"


def test_a_site_that_does_not_exist_is_flagged(net):
    net.dns_missing.add("example.com")
    assert verdict() == "unreachable"


@pytest.mark.parametrize("failure", ["refused", "slow"])
def test_a_site_that_refuses_or_is_too_slow_is_flagged(net, failure):
    net.routes["example.com/page"] = failure
    assert verdict() == "unreachable"


def test_redirects_are_followed(net):
    net.routes["example.com/page"] = (301, "https://www.example.com/new")
    net.routes["www.example.com/new"] = (302, "/final")
    assert verdict() == "ok"
    assert net.calls == ["example.com/page", "www.example.com/new", "www.example.com/final"]
    net.routes["www.example.com/final"] = 404
    assert verdict() == "unreachable"  # the end of the chain is what counts


def test_an_endless_redirect_is_not_held_against_the_site(net):
    net.routes["example.com/page"] = (302, "/page")
    assert verdict() == "ok" and len(net.calls) == linkcheck.MAX_HOPS


def test_addresses_inside_a_private_network_are_never_called(net):
    for private in ("10.0.0.5", "127.0.0.1", "192.168.1.1", "169.254.169.254", "::1"):
        net.addresses["example.com"] = private
        net.calls.clear()
        assert verdict() == "ok" and net.calls == [], private


def test_a_redirect_into_a_private_network_is_not_followed(net):
    net.routes["example.com/page"] = (302, "http://internal.test/admin")
    net.addresses["internal.test"] = "10.1.2.3"
    assert verdict() == "ok"
    assert net.calls == ["example.com/page"]  # the second step was never requested


def test_a_redirect_to_a_non_web_address_is_not_followed(net):
    net.routes["example.com/page"] = (302, "ftp://example.com/file")
    assert verdict() == "ok" and net.calls == ["example.com/page"]


def test_a_check_that_takes_too_long_gives_up_quietly(net, monkeypatch):
    monkeypatch.setattr(settings, "link_check_budget", 0)
    assert probe("https://example.com/page") == "unsure" and net.calls == []


def test_the_check_can_be_switched_off(net, monkeypatch):
    monkeypatch.setattr(settings, "link_check", False)
    net.routes["example.com/page"] = 404
    assert verdict() == "skipped" and net.calls == []


# ---- Google Safe Browsing ---------------------------------------------------------------


def test_safe_browsing_matches_are_refused(net, monkeypatch):
    monkeypatch.setattr(settings, "safe_browsing_key", "k")
    sent = []

    def handler(request):
        sent.append(request)
        if request.url.host == "safebrowsing.googleapis.com":
            return httpx.Response(200, json={"matches": [{"threatType": "MALWARE"}]})
        return httpx.Response(200)

    monkeypatch.setattr(linkcheck, "_TRANSPORT", httpx.MockTransport(handler))
    result = check_destination("https://example.com/page")
    assert result.verdict == "blocked" and result.reason == "safe browsing"
    assert sent[0].url.params["key"] == "k" and len(sent) == 1  # no need to fetch the page
    assert b"example.com/page" in sent[0].content


def test_no_matches_means_carry_on(net, monkeypatch):
    monkeypatch.setattr(settings, "safe_browsing_key", "k")
    def handler(request):
        is_google = "googleapis" in request.url.host
        return httpx.Response(200, json={}) if is_google else httpx.Response(200)

    monkeypatch.setattr(linkcheck, "_TRANSPORT", httpx.MockTransport(handler))
    assert verdict() == "ok"


@pytest.mark.parametrize("reply", [httpx.Response(500), httpx.Response(200, text="not json")])
def test_a_safe_browsing_failure_never_blocks_a_link(net, monkeypatch, reply):
    monkeypatch.setattr(settings, "safe_browsing_key", "k")
    monkeypatch.setattr(linkcheck, "_TRANSPORT", httpx.MockTransport(lambda r: reply))
    assert linkcheck.safe_browsing_hit("https://example.com") is False


def test_without_a_key_safe_browsing_is_not_called(net):
    assert linkcheck.safe_browsing_hit("https://example.com") is False and net.calls == []


# ---- when a link is created ---------------------------------------------------------------


def make(client, slug="lnk", url="https://example.com/page", **extra):
    return client.post("/dashboard/links", data={"original_url": url, "slug": slug, **extra})


def count_links(app):
    with app.state.session_factory() as db:
        return db.query(Link).count()


def test_a_working_destination_makes_a_link_without_a_warning(alice, net):
    make(alice)
    page = alice.get("/dashboard").text
    assert "Created" in page and "flash warn" not in page


def test_a_destination_that_does_not_answer_still_makes_the_link_but_warns(alice, net, app):
    net.routes["example.com/page"] = 404
    make(alice)
    assert count_links(app) == 1
    page = alice.get("/dashboard").text
    assert re.search(r'class="flash warn"[^>]*>[^<]*' + NO_ANSWER, page)
    assert "Created" in page


def test_an_unsafe_destination_is_refused(alice, net, app, monkeypatch):
    monkeypatch.setattr(settings, "blocked_domains", ("phish.test",))
    make(alice, url="https://login.phish.test/bank")
    assert count_links(app) == 0
    page = alice.get("/dashboard").text
    assert UNSAFE in unescape(page) and 'class="flash error"' in page and "Created" not in page
    assert net.calls == []  # nothing was fetched


def test_safe_browsing_blocks_creation(alice, net, app, monkeypatch):
    monkeypatch.setattr(settings, "safe_browsing_key", "k")
    monkeypatch.setattr(linkcheck, "_TRANSPORT", httpx.MockTransport(
        lambda r: httpx.Response(200, json={"matches": [{}]})))
    make(alice)
    assert count_links(app) == 0 and UNSAFE in unescape(alice.get("/dashboard").text)


def test_a_bad_address_is_still_refused_before_any_check(alice, net, app):
    make(alice, url="http://127.0.0.1/admin")
    assert count_links(app) == 0 and net.calls == []


# ---- when the destination is edited ------------------------------------------------------


def edit(client, app, url, slug="lnk"):
    with app.state.session_factory() as db:
        lid = db.query(Link).filter_by(slug=slug).one().id
    return client.post(f"/dashboard/links/{lid}/edit",
                       data={"original_url": url, "password_action": "keep"})


def destination(app, slug="lnk"):
    with app.state.session_factory() as db:
        return db.query(Link).filter_by(slug=slug).one().original_url


def test_editing_checks_only_a_new_destination(alice, net, app):
    make(alice)
    net.calls.clear()
    edit(alice, app, "https://example.com/page")  # the same address
    assert net.calls == []
    edit(alice, app, "https://example.com/other")
    assert net.calls == ["example.com/other"]


def test_editing_to_a_silent_destination_saves_but_warns(alice, net, app):
    make(alice)
    net.routes["example.com/other"] = 500
    edit(alice, app, "https://example.com/other")
    assert destination(app) == "https://example.com/other"
    assert NO_ANSWER in alice.get("/dashboard").text


def test_editing_to_an_unsafe_destination_is_refused(alice, net, app, monkeypatch):
    make(alice)
    monkeypatch.setattr(settings, "blocked_domains", ("phish.test",))
    r = edit(alice, app, "https://phish.test/x")
    assert r.status_code == 303 and destination(app) == "https://example.com/page"
    assert UNSAFE in unescape(alice.get("/dashboard/links/1/edit").text)


@pytest.mark.parametrize("lang, word", [("hi", "असुरक्षित"), ("gu", "અસુરક્ષિત")])
def test_the_messages_are_translated(alice, net, app, monkeypatch, lang, word):
    monkeypatch.setattr(settings, "blocked_domains", ("phish.test",))
    alice.post("/language", data={"lang": lang, "next": "/"})
    make(alice, url="https://phish.test/x")
    assert word in alice.get("/dashboard").text
    net.routes["example.com/c"] = 404
    make(alice, slug="ccc", url="https://example.com/c")
    page = alice.get("/dashboard").text
    assert "flash warn" in page and NO_ANSWER not in page  # a warning, but not in English
