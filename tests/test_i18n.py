"""Languages: English, Hindi (Devanagari) and Gujarati."""
import ast
import json
import re
from pathlib import Path

import pytest

from app import i18n
from app.i18n import (
    CATALOGS,
    EXTRA_KEYS,
    JS_STRINGS,
    LANGUAGES,
    detect_language,
    js_data,
    translate,
    translate_html,
    translate_plural,
)
from app.models import User
from app.routers.language import safe_next
from tests.conftest import register

APP = Path(__file__).resolve().parent.parent / "app"
PW = "password123"
DEVANAGARI = re.compile(r"[\u0900-\u097F]")
GUJARATI = re.compile(r"[\u0A80-\u0AFF]")
SAME_AS_ENGLISH = {"QR"}  # fine to leave as is


# ---------- find every sentence the code asks to translate ----------

def _unescape(text: str) -> str:
    return text.replace("\\'", "'").replace('\\"', '"').replace("\\n", "\n")


TEMPLATE_CALL = re.compile(
    r"""\b_[nh]?\(\s*(?P<q>["'])(?P<a>(?:\\.|(?!(?P=q)).)*)(?P=q)"""
    r"""(?:\s*,\s*(?P<q2>["'])(?P<b>(?:\\.|(?!(?P=q2)).)*)(?P=q2))?""",
    re.S,
)


def template_strings() -> set[str]:
    found = set()
    for path in (APP / "templates").glob("*.html"):
        for m in TEMPLATE_CALL.finditer(path.read_text(encoding="utf-8")):
            found.add(_unescape(m.group("a")))
            if m.group("b"):
                found.add(_unescape(m.group("b")))
    return found


def python_strings() -> tuple[set[str], list[str]]:
    """Messages passed to flash/back/HTTPException/ValueError/error=. Also reports f-strings."""
    found, problems = set(), []

    def take(node, where):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.add(node.value)
        elif isinstance(node, ast.JoinedStr):
            problems.append(f"{where}: use a {{placeholder}} instead of an f-string")

    for path in APP.rglob("*.py"):
        if "locales" in path.parts or path.name == "i18n.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            where = f"{path.relative_to(APP)}:{getattr(node, 'lineno', '?')}"
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
                if name == "flash" and len(node.args) > 1:
                    take(node.args[1], where)
                elif name == "back":
                    for arg in node.args[:2]:
                        if isinstance(arg, (ast.Constant, ast.JoinedStr)):
                            take(arg, where)
                            break
                elif name == "HTTPException" and len(node.args) > 1:
                    take(node.args[1], where)
                elif name == "ValueError" and node.args:
                    take(node.args[0], where)
                for kw in node.keywords:
                    if kw.arg == "error":
                        take(kw.value, where)
            elif isinstance(node, ast.FunctionDef) and node.name == "password_error":
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Return) and sub.value is not None:
                        take(sub.value, where)
    return found, problems


def expected_keys() -> set[str]:
    py, _ = python_strings()
    return template_strings() | py | set(JS_STRINGS.values()) | set(EXTRA_KEYS)


def placeholders(text: str) -> set[str]:
    return set(re.findall(r"\{(\w+)\}", text))


# ---------- the catalogs ----------

def test_no_f_strings_in_translatable_messages():
    assert python_strings()[1] == []


def test_scanner_finds_the_sentences(  # guards the guard: the scan itself must not break
):
    keys = expected_keys()
    assert len(keys) > 150
    for sample in ("Your links", "Wrong password. Try again.", "{n} total clicks", "Created {url}"):
        assert sample in keys


@pytest.mark.parametrize("lang", ["hi", "gu"])
def test_every_sentence_is_translated(lang):
    missing = sorted(expected_keys() - set(CATALOGS[lang]))
    assert missing == [], f"missing in {lang}: {missing}"


@pytest.mark.parametrize("lang", ["hi", "gu"])
def test_no_unused_translations(lang):
    unused = sorted(set(CATALOGS[lang]) - expected_keys())
    assert unused == [], f"unused in {lang}: {unused}"


@pytest.mark.parametrize("lang", ["hi", "gu"])
def test_placeholders_match_english(lang):
    for english, text in CATALOGS[lang].items():
        assert placeholders(english) == placeholders(text), english


@pytest.mark.parametrize("lang,script", [("hi", DEVANAGARI), ("gu", GUJARATI)])
def test_translations_are_in_the_right_script(lang, script):
    for english, text in CATALOGS[lang].items():
        if english in SAME_AS_ENGLISH:
            continue
        assert text.strip() and text != english, english
        assert script.search(text), f"{english!r} -> {text!r}"


def test_both_catalogs_have_the_same_sentences():
    assert set(CATALOGS["hi"]) == set(CATALOGS["gu"])


def test_calendar_names_are_complete():
    for lang in LANGUAGES:
        assert len(i18n.MONTHS[lang]) == 12 and len(set(i18n.MONTHS[lang])) == 12
        assert len(i18n.WEEKDAYS[lang]) == 7 and len(i18n.WEEKDAYS_SHORT[lang]) == 7


# ---------- helpers ----------

def test_translate_and_fallbacks():
    assert translate("hi", "Log in") == "लॉग इन"
    assert translate("gu", "Log in") == "લૉગ ઇન"
    assert translate("en", "Log in") == "Log in"
    assert translate("fr", "Log in") == "Log in"                      # unknown language
    assert translate("hi", "Not in the catalog") == "Not in the catalog"
    assert "x" in translate("hi", "Created {url}", url="x")
    assert translate("hi", "Select {slug}", slug="abc") == "abc चुनें"


def test_plural_and_html_helpers():
    assert translate_plural("en", "{n} link", "{n} links", 1) == "1 link"
    assert translate_plural("en", "{n} link", "{n} links", 3) == "3 links"
    assert translate_plural("hi", "{n} link", "{n} links", 3) == "3 लिंक"
    html = translate_html("en", "Current email: {email}", email="<script>x</script>")
    assert "&lt;script&gt;" in html and "<script>" not in html     # plain params are escaped


def test_detect_language():
    assert detect_language("hi-IN,hi;q=0.9,en;q=0.8") == "hi"
    assert detect_language("GU") == "gu"
    assert detect_language("fr-FR,fr;q=0.9,gu;q=0.5") == "gu"
    assert detect_language("fr, de") == "en"
    assert detect_language("") == "en"


def test_safe_next_blocks_open_redirects():
    assert safe_next("/dashboard") == "/dashboard"
    for bad in ("", "https://evil.example", "//evil.example", "/\\evil.example", "evil", "/a\nb"):
        assert safe_next(bad) == "/"


def test_js_data_for_the_picker():
    data = js_data("hi")
    assert data["months"][0] == "जनवरी" and data["weekdays"][0] == "रविवार"
    assert data["ui"]["done"] == "हो गया"
    assert set(data["ui"]) == set(JS_STRINGS)
    assert "{example}" in data["ui"]["bad_date"]  # filled in by the browser


# ---------- choosing a language on the site ----------

def test_english_is_the_default(client):
    page = client.get("/login").text
    assert '<html lang="en"' in page and "Username or email" in page


@pytest.mark.parametrize("lang,sample", [("hi", "यूज़रनेम या ईमेल"), ("gu", "યુઝરનેમ અથવા ઇમેઇલ")])
def test_cookie_selects_language(client, lang, sample):
    client.cookies.set("lang", lang)
    page = client.get("/login").text
    assert f'<html lang="{lang}"' in page and sample in page


def test_browser_language_is_used_when_there_is_no_cookie(client):
    hindi = client.get("/login", headers={"accept-language": "hi-IN,hi;q=0.9"}).text
    assert "यूज़रनेम या ईमेल" in hindi
    client.cookies.set("lang", "gu")  # the saved choice beats the browser
    assert "યુઝરનેમ" in client.get("/login", headers={"accept-language": "hi"}).text


def test_switching_sets_cookie_and_returns_to_the_page(client):
    r = client.post("/language", data={"lang": "hi", "next": "/login"})
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert "lang=hi" in r.headers["set-cookie"]
    assert "यूज़रनेम" in client.get("/login").text


def test_switching_cannot_redirect_elsewhere_or_use_unknown_languages(client):
    r = client.post("/language", data={"lang": "gu", "next": "https://evil.example/x"})
    assert r.headers["location"] == "/"                       # sent home, not to the other site
    r = client.post("/language", data={"lang": "klingon", "next": "/login"})
    assert r.headers["location"] == "/login" and "lang=" not in r.headers.get("set-cookie", "")
    assert "યુઝરનેમ" in client.get("/login").text  # still Gujarati: unknown language ignored


def test_language_is_saved_on_the_account_and_follows_the_user(alice, make_client, app):
    alice.post("/language", data={"lang": "gu", "next": "/dashboard"})
    with app.state.session_factory() as db:
        assert db.query(User).filter_by(username="alice").one().language == "gu"
    other_device = make_client()  # fresh browser: no cookie, no browser language
    assert "Username or email" in other_device.get("/login").text
    other_device.post("/login", data={"identifier": "alice", "password": PW})
    assert "ડેશબોર્ડ" in other_device.get("/dashboard").text  # Gujarati came back at login


def test_new_accounts_start_in_the_visitors_language(client, app):
    client.cookies.set("lang", "hi")
    register(client, "ravi")
    with app.state.session_factory() as db:
        assert db.query(User).filter_by(username="ravi").one().language == "hi"
    assert "डैशबोर्ड" in client.get("/dashboard").text


def test_logging_out_keeps_the_language(alice):
    alice.post("/language", data={"lang": "hi", "next": "/"})
    alice.post("/logout")
    assert "यूज़रनेम" in alice.get("/login").text


# ---------- translated pages and messages ----------

def test_messages_after_actions_are_translated(alice):
    alice.post("/language", data={"lang": "hi", "next": "/"})
    wrong = {"current_password": "wrong-pass", "new_password": "x" * 9}
    alice.post("/account/password", data=wrong)
    assert "यह पासवर्ड सही नहीं है।" in alice.get("/account").text
    alice.post("/dashboard/links", data={"original_url": "https://example.com", "slug": "hello"})
    assert "बना दिया:" in alice.get("/dashboard").text            # message with a {url} inside


def test_validation_messages_are_translated(alice):
    alice.post("/language", data={"lang": "gu", "next": "/"})
    alice.post("/dashboard/links", data={"original_url": "ftp://example.com", "slug": "bad"})
    assert "ફક્ત http અને https લિંકની મંજૂરી છે." in alice.get("/dashboard").text


def test_error_pages_are_translated(client):
    client.cookies.set("lang", "hi")
    assert "यह छोटा लिंक मौजूद नहीं है।" in client.get("/nobody/nothing").text
    assert "नहीं मिला" in client.get("/no-such-page").text
    client.cookies.set("lang", "gu")
    assert "આ ટૂંકી લિંક અસ્તિત્વમાં નથી." in client.get("/nobody/nothing").text


def test_link_gate_and_password_page_are_translated(alice):
    alice.post("/dashboard/links", data={"original_url": "https://example.com", "slug": "vip",
                                         "link_password": "open-sesame"})
    alice.post("/language", data={"lang": "hi", "next": "/"})
    assert "यह लिंक सुरक्षित है" in alice.get("/alice/vip").text
    assert "गलत पासवर्ड। फिर कोशिश करें।" in alice.post("/alice/vip", data={"password": "no"}).text


def test_counts_use_singular_and_plural(alice):
    alice.post("/dashboard/links", data={"original_url": "https://example.com", "slug": "one1"})
    assert "1 link · 0 total clicks" in alice.get("/dashboard").text
    alice.post("/dashboard/links", data={"original_url": "https://example.org", "slug": "two2"})
    assert "2 links" in alice.get("/dashboard").text
    alice.post("/language", data={"lang": "hi", "next": "/"})
    assert "2 लिंक · कुल 0 क्लिक" in alice.get("/dashboard").text


PAGES = ["/dashboard", "/dashboard/links/1/edit", "/dashboard/links/1", "/account"]


@pytest.mark.parametrize("url", PAGES)
@pytest.mark.parametrize("lang", ["hi", "gu"])
def test_signed_in_pages_render_in_every_language(alice, url, lang):
    alice.post("/dashboard/links", data={"original_url": "https://example.com", "slug": "page1"})
    alice.post("/language", data={"lang": lang, "next": "/"})
    page = alice.get(url)
    assert page.status_code == 200 and f'<html lang="{lang}"' in page.text
    script = DEVANAGARI if lang == "hi" else GUJARATI
    assert script.search(page.text)


def test_pages_still_render_without_a_cookie_or_session(client):
    for lang in ("hi", "gu"):
        client.cookies.set("lang", lang)
        for url in ("/", "/login", "/register"):
            assert client.get(url).status_code == 200


def test_admin_page_still_works_in_other_languages(alice, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "admin_usernames", {"alice"})
    alice.post("/language", data={"lang": "hi", "next": "/"})
    assert alice.get("/admin").status_code == 200


def test_verification_email_is_sent_in_the_users_language(alice, monkeypatch):
    from app.config import settings

    outbox = []
    monkeypatch.setattr(settings, "email_backend", "console")
    monkeypatch.setattr("app.routers.account.send_email",
                        lambda to, subject, body: outbox.append((subject, body)) or True)
    alice.post("/language", data={"lang": "hi", "next": "/"})
    alice.post("/account/email/request", data={"new_email": "new@example.com", "password": PW})
    subject, body = outbox[-1]
    assert subject == "आपका Link Shortener सत्यापन कोड"
    assert re.search(r"\b\d{6}\b", body) and "मिनट" in body


def test_user_input_inside_translated_sentences_is_escaped(alice, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "email_backend", "console")
    monkeypatch.setattr("app.routers.account.send_email", lambda *a: True)
    alice.post("/account/email/request", data={"new_email": "<i>x@example.com", "password": PW})
    page = alice.get("/account/email/verify").text
    assert "&lt;i&gt;x@example.com" in page and "<i>x@example.com" not in page


# ---------- the new top bar ----------

def test_dashboard_link_sits_next_to_the_logo_and_language_button_before_the_avatar(alice):
    page = alice.get("/dashboard").text
    start = page.index('class="topbar-left"')
    left = page[start:page.index("</div>", start)]
    assert 'class="brand"' in left and 'class="navlink"' in left
    assert left.index('class="brand"') < left.index('class="navlink"')
    right = page[page.index('class="topbar-right"'):]
    assert 'class="navlink"' not in right
    assert right.index("langmenu") < right.index('id="usermenu"')


def test_language_button_shows_the_current_language_in_its_own_script(alice):
    english = alice.get("/dashboard").text
    assert '<span class="lang-name">English</span>' in english
    alice.post("/language", data={"lang": "hi", "next": "/"})
    hindi = alice.get("/dashboard").text
    assert '<span class="lang-name">हिन्दी</span>' in hindi
    for name in ("English", "हिन्दी", "ગુજરાતી"):
        assert f"<span>{name}</span>" in hindi
    assert 'name="lang" value="gu"' in hindi and 'name="next" value="/dashboard"' in hindi


def test_language_button_is_there_for_visitors_too(client):
    page = client.get("/login").text
    assert "langmenu" in page and 'name="lang" value="hi"' in page


def test_picker_gets_its_language_data(client):
    client.cookies.set("lang", "gu")
    page = client.get("/login").text
    blob = re.search(r'<script type="application/json" id="i18n-data">(.*?)</script>', page, re.S)
    data = json.loads(blob.group(1))
    assert data["lang"] == "gu" and data["months"][0] == "જાન્યુઆરી"


def test_logo_and_dashboard_link_share_a_text_baseline():
    css = (APP / "static" / "style.css").read_text(encoding="utf-8")
    rule = re.search(r"\.topbar-left\s*\{([^}]*)\}", css).group(1)
    assert "align-items: baseline" in rule  # centring the boxes left the smaller text sitting high
