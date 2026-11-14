"""Translations. The English sentence is the key; a missing translation falls back to English.

    translate("hi", "Log in")                      -> "लॉग इन"
    translate("hi", "Created {url}", url="x")      -> "बना दिया: x"
"""
from datetime import date

from markupsafe import Markup

from .locales import gu, hi

LANGUAGES = {"en": "English", "hi": "हिन्दी", "gu": "ગુજરાતી"}  # each in its own script
# Letters on the language button: (big = the language you are using, small = the other one).
LANGUAGE_ICONS = {"en": ("A", "अ"), "hi": ("अ", "A"), "gu": ("અ", "A")}
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
MONTHS_SHORT = {  # for chart labels and the day-by-day log
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "hi": ["जन॰", "फ़र॰", "मार्च", "अप्रैल", "मई", "जून", "जुल॰", "अग॰", "सित॰", "अक्तू॰", "नव॰", "दिस॰"],
    "gu": ["જાન્યુ", "ફેબ્રુ", "માર્ચ", "એપ્રિલ", "મે", "જૂન", "જુલાઈ", "ઑગસ્ટ", "સપ્ટે", "ઑક્ટો",
           "નવે", "ડિસે"],
}
# The ten digits 0-9 written in each language's own script (English keeps 0-9).
DIGITS = {"hi": "०१२३४५६७८९", "gu": "૦૧૨૩૪૫૬૭૮૯"}
_TO_NATIVE = {lang: str.maketrans("0123456789", digits) for lang, digits in DIGITS.items()}
_TO_ASCII = {ord(c): str(i) for digits in DIGITS.values() for i, c in enumerate(digits)}
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
    "share_copied": "Copied!",
    "share_copy_failed": "Could not copy automatically. Select the link and copy it.",
    "photo_choose": "Please choose a photo first.",
    "photo_invalid": "That file is not a valid photo. Please use a JPEG, PNG or WebP image.",
    "photo_camera_failed": "We could not open the camera. You can upload a photo instead.",
    "photo_saving": "Saving…",
    "photo_failed": "The photo could not be saved. Please try again.",
    "camera_blocked": "Camera access is blocked. Click the camera icon in the address bar, "
                      "choose Allow, then try again.",
    "camera_missing": "No camera was found on this device.",
    "camera_busy": "Your camera is being used by another app. Close it and try again.",
}

# Texts of the emails we send.
EMAIL_SUBJECT = "Your Link Shortener verification code"
EMAIL_BODY = (
    "Your Link Shortener verification code is {code}.\n\nIt expires in 10 minutes. "
    "If you did not ask to change your email, you can ignore this message."
)
SIGNUP_EMAIL_SUBJECT = "Your Link Shortener sign-up code"
SIGNUP_EMAIL_BODY = (
    "Your Link Shortener sign-up code is {code}.\n\nIt expires in 10 minutes. "
    "If you did not try to sign up, you can ignore this message."
)

# Sentences that are looked up dynamically (so a text scan cannot find them).
EXTRA_KEYS = [
    "desktop", "mobile", "tablet", "bot", "Direct",
    "Other websites", "Unknown", "Other", "In-app browser",  # used by app/insights.py
    "Not Found", "Method Not Allowed",
    "Cat", "Dog", "Fox", "Panda", "Rabbit", "Bear", "Frog", "Owl", "Penguin", "Pig", "Lion",
    "Tiger", "Monkey", "Koala", "Mouse", "Chicken", "Duck", "Elephant", "Wolf", "Raccoon",
    "Hamster", "Deer", "Giraffe", "Zebra", "Cow", "Sheep", "Hedgehog", "Turtle", "Bat", "Octopus",
    "Ladybug", "Bee", "Parrot", "Crocodile", "Whale", "Sloth",
    EMAIL_SUBJECT, EMAIL_BODY, SIGNUP_EMAIL_SUBJECT, SIGNUP_EMAIL_BODY,
]


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


def native_digits(lang: str, value) -> str:
    """Write the digits of `value` in the language's own script: 12 -> '१२' (hi) or '૧૨' (gu)."""
    table = _TO_NATIVE.get(lang)
    return str(value).translate(table) if table else str(value)


def ascii_digits(text: str) -> str:
    """The reverse: Hindi/Gujarati digits back to 0-9 (for reading what a person typed)."""
    return text.translate(_TO_ASCII)


def format_date(day: date, lang: str, *, year: bool = False) -> str:
    """'09 Nov', or '09 Nov 2026' with year=True. Month names and digits follow the language."""
    months = MONTHS_SHORT.get(lang, MONTHS_SHORT[DEFAULT_LANGUAGE])
    text = f"{day.day:02d} {months[day.month - 1]}" + (f" {day.year}" if year else "")
    return native_digits(lang, text)


def _translated(lang: str, text: str) -> str:
    """The sentence in the language, its digits in that language's script. English: unchanged.

    Only real translations are touched; a sentence with no translation is shown as it is.
    """
    catalog = CATALOGS.get(lang, {})
    return native_digits(lang, catalog[text]) if text in catalog else text


def _numbers(lang: str, params: dict) -> dict:
    """Whole numbers fill the sentence in the language's digits. Text (names, codes) is kept."""
    return {
        key: native_digits(lang, value) if isinstance(value, int) and not isinstance(value, bool)
        else value
        for key, value in params.items()
    }


def translate(lang: str, text: str, **params) -> str:
    message = _translated(lang, text)
    return message.format(**_numbers(lang, params)) if params else message


def translate_plural(lang: str, singular: str, plural: str, n: int) -> str:
    return translate(lang, singular if n == 1 else plural, n=n)


def translate_html(lang: str, text: str, **params) -> Markup:
    """Like translate(), for sentences that contain trusted HTML. Plain params are escaped."""
    message = _translated(lang, text)
    return Markup(message).format(**_numbers(lang, params)) if params else Markup(message)


def js_data(lang: str) -> dict:
    lang = lang if lang in LANGUAGES else DEFAULT_LANGUAGE
    return {
        "lang": lang,
        "digits": DIGITS.get(lang, ""),  # "" = keep 0-9
        "months": MONTHS[lang],
        "weekdays": WEEKDAYS[lang],
        "short": WEEKDAYS_SHORT[lang],
        "ui": {key: translate(lang, text) for key, text in JS_STRINGS.items()},
    }
