"""Import links from a CSV file (the counterpart of Export CSV).

Every row goes through the same checks as the create form. A bad row is skipped and listed with
the reason; the good rows are still imported. Passwords are never imported, and destinations are
not fetched to see whether they answer (that would take too long for a whole file), but the
unsafe-sites list is applied.
"""

import csv
import io
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .features import require
from .i18n import translate
from .linkcheck import UNSAFE_MESSAGE, host_blocked
from .models import Link, User, utcnow
from .tags import parse_tags, set_link_tags
from .utils import (
    csv_safe_undo,
    generate_slug,
    parse_click_limit,
    parse_moment,
    validate_slug,
    validate_url,
)

MAX_IMPORT_ROWS = 200
MAX_IMPORT_BYTES = 500 * 1024
URL_COLUMNS = ("original_url", "url", "long_url", "destination")
TEMPLATE_ROWS = [
    ["original_url", "slug", "starts_at", "expires_at", "click_limit", "tags", "active"],
    ["https://example.com/summer-sale", "summer", "", f"{date.today().year + 1}-12-31", "",
     "work, social", "yes"],
    ["https://example.com/one-time-offer", "", "", "", "1", "", "yes"],
]
OFF_WORDS = ("no", "false", "0", "off", "inactive")


NO_HEADER = "The first row must hold the column names, including original_url."


class RowError(ValueError):
    """A problem with one row. `params` fill the {placeholders} of the message."""

    def __init__(self, message: str, **params):
        super().__init__(message)
        self.params = params


@dataclass
class ImportResult:
    created: int = 0
    skipped: list[dict] = field(default_factory=list)  # {"line", "url", "why"}


def read_rows(data: bytes) -> list[tuple[int, dict[str, str]]]:
    """The file's rows as (line number, {column: text}). Raises ValueError for a bad file."""
    if len(data) > MAX_IMPORT_BYTES:
        raise ValueError("That file is too big. The most is 500 KB.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("That is not a text (UTF-8) CSV file.") from None
    reader = csv.reader(io.StringIO(text))
    try:
        header = [h.strip().lower() for h in next(reader)]
    except (StopIteration, csv.Error):
        raise ValueError(NO_HEADER) from None
    url_col = next((c for c in URL_COLUMNS if c in header), None)
    if url_col is None:
        raise ValueError(NO_HEADER)
    rows = []
    try:
        for number, cells in enumerate(reader, start=2):
            if not any(c.strip() for c in cells):
                continue  # a blank line
            record = {h: (cells[i].strip() if i < len(cells) else "") for i, h in enumerate(header)}
            record["original_url"] = record[url_col]
            rows.append((number, record))
    except csv.Error:
        raise ValueError("That is not a text (UTF-8) CSV file.") from None
    if not rows:
        raise ValueError("The file has no links in it.")
    if len(rows) > MAX_IMPORT_ROWS:
        raise ValueError("A file can have up to 200 links. Split it into smaller files.")
    return rows


def _active(raw: str) -> bool:
    return raw.strip().lower() not in OFF_WORDS


def _read_row(user: User, row: dict[str, str], own_host: str) -> dict:
    """Check one row and return its cleaned values. Raises ValueError / RowError."""
    url = validate_url(csv_safe_undo(row["original_url"]), blocked_hosts=(own_host,))
    if host_blocked(urlparse(url).hostname or ""):
        raise ValueError(UNSAFE_MESSAGE)
    start = parse_moment(csv_safe_undo(row.get("starts_at", "")), "")
    end = parse_moment(csv_safe_undo(row.get("expires_at", "")), "", end_of_day=True)
    if start and end and start >= end:
        raise ValueError("The end time must be after the start time.")
    if end and end <= utcnow():
        raise ValueError("The end time must be in the future.")
    limit = parse_click_limit(row.get("click_limit", ""))
    names = parse_tags(csv_safe_undo(row.get("tags", "")))
    if limit is not None:
        require(user, "click_limit")
    if names:
        require(user, "tags")
    slug = csv_safe_undo(row.get("slug", "")).strip()
    return {
        "url": url, "start": start, "end": end, "limit": limit, "names": names,
        "slug": validate_slug(slug) if slug else "", "active": _active(row.get("active", "yes")),
    }


def import_links(
    db: Session, user: User, rows: list[tuple[int, dict[str, str]]], lang: str, own_host: str
) -> ImportResult:
    result = ImportResult()
    taken = set(db.scalars(select(Link.slug).where(Link.user_id == user.id)))
    for number, row in rows:
        try:
            values = _read_row(user, row, own_host)
            slug = values["slug"]
            if slug and slug in taken:
                raise RowError("You already have a link called '{slug}'.", slug=slug)
            if not slug:
                slug = next((s for s in (generate_slug() for _ in range(10)) if s not in taken), "")
                if not slug:
                    raise RowError("Could not generate a unique code. Try again.")
            link = Link(
                user_id=user.id, slug=slug, original_url=values["url"], starts_at=values["start"],
                expires_at=values["end"], click_limit=values["limit"], is_active=values["active"],
            )
            with db.begin_nested():  # a failing row undoes only itself
                set_link_tags(db, user, link, values["names"])
                db.add(link)
                db.flush()
        except IntegrityError:
            result.skipped.append(_skip(number, row, translate(
                lang, "You already have a link called '{slug}'.", slug=values["slug"])))
        except RowError as e:
            result.skipped.append(_skip(number, row, translate(lang, str(e), **e.params)))
        except ValueError as e:
            result.skipped.append(_skip(number, row, translate(lang, str(e))))
        else:
            taken.add(slug)
            result.created += 1
    db.commit()
    return result


def _skip(number: int, row: dict[str, str], why: str) -> dict:
    return {"line": number, "url": row.get("original_url", "")[:80], "why": why}
