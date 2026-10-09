"""Translations. The English sentence is the key; a missing translation falls back to English.

    translate("hi", "Log in")                      -> "लॉग इन"
    translate("hi", "Created {url}", url="x")      -> "बना दिया: x"
"""
from markupsafe import Markup

from .locales import gu, hi

LANGUAGES = {"en": "English", "hi": "हिन्दी", "gu": "ગુજરાતી"}  # each in its own script
DEFAULT_LANGUAGE = "en"
CATALOGS = {"hi": hi.MESSAGES, "gu": gu.MESSAGES}

MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"],
    "hi": ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त",
           "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"],
    "gu": ["જાન્યુઆરી", "ફેબ્રુઆરી", "માર્ચ", "એપ્રિલ", "મે", "જૂન", "જુલાઈ", "ઑગસ્ટ",
           "સપ્ટેમ્બર", "ઑક્ટોબર", "નવેમ્બર", "ડિસેમ્બર"],
}
WEEKDAYS = {  # Sunday first
    "en": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
    "hi": ["रविवार", "सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार"],
    "gu": ["રવિવાર", "સોમવાર", "મંગળવાર", "બુધવાર", "ગુરુવાર", "શુક્રવાર", "શનિવાર"],
}
WEEKDAYS_SHORT = {
    "en": ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"],
    "hi": ["रवि", "सोम", "मंगल", "बुध", "गुरु", "शुक्र", "शनि"],
    "gu": ["રવિ", "સોમ", "મંગળ", "બુધ", "ગુરુ", "શુક્ર", "શનિ"],
}

# Text used by the date picker script (sent to the browser as JSON).
JS_STRINGS = {
    "prev_month": "Previous month",
    "next_month": "Next month",
    "month": "Month",
    "year": "Year",
    "days": "Days",
    "time": "Time",
    "hour": "Hour",
    "minute": "Minute",
    "second": "Second",
    "clear": "Clear",
    "today": "Today",
    "done": "Done",
    "choose_start": "Choose start date and time",
    "choose_end": "Choose end date and time",
    "bad_date": "Use a date like {example}, optionally with a time like 09:30 PM.",
    "example": "e.g. {example}",
}

# Sentences that are looked up dynamically (so a text scan cannot find them).
EXTRA_KEYS = [
    "desktop", "mobile", "tablet", "bot", "Direct",
    "Not Found", "Method Not Allowed",
    "Cat", "Dog", "Fox", "Panda", "Rabbit", "Bear", "Frog", "Owl", "Penguin", "Pig", "Lion",
    "Tiger", "Monkey", "Koala", "Mouse", "Chicken", "Duck", "Elephant", "Wolf", "Raccoon",
    "Your Link Shortener verification code",
    "Your Link Shortener verification code is {code}.\n\nIt expires in 10 minutes. "
    "If you did not ask to change your email, you can ignore this message.",
]

EMAIL_SUBJECT = EXTRA_KEYS[-2]
EMAIL_BODY = EXTRA_KEYS[-1]


def detect_language(accept_language: str) -> str:
    """Pick a supported language from a browser's Accept-Language header."""
    for part in (accept_language or "").split(","):
        code = part.split(";")[0].strip().lower().split("-")[0]
        if code in LANGUAGES:
            return code
    return DEFAULT_LANGUAGE


def get_lang(request) -> str:
    """The visitor's language: their saved choice, else their browser's, else English."""
    code = request.cookies.get("lang")
    if code in LANGUAGES:
        return code
    return detect_language(request.headers.get("accept-language", ""))


def translate(lang: str, text: str, **params) -> str:
    message = CATALOGS.get(lang, {}).get(text, text)
    return message.format(**params) if params else message


def translate_plural(lang: str, singular: str, plural: str, n: int) -> str:
    return translate(lang, singular if n == 1 else plural, n=n)


def translate_html(lang: str, text: str, **params) -> Markup:
    """Like translate(), for sentences that contain trusted HTML. Plain params are escaped."""
    message = CATALOGS.get(lang, {}).get(text, text)
    return Markup(message).format(**params) if params else Markup(message)


def js_data(lang: str) -> dict:
    lang = lang if lang in LANGUAGES else DEFAULT_LANGUAGE
    return {
        "lang": lang,
        "months": MONTHS[lang],
        "weekdays": WEEKDAYS[lang],
        "short": WEEKDAYS_SHORT[lang],
        "ui": {key: translate(lang, text) for key, text in JS_STRINGS.items()},
    }
