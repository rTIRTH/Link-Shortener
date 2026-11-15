"""Tags: short labels that group a user's links (work, social, school ...)."""

import hashlib
import re

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import Link, Tag, User, link_tags

MAX_TAG_LENGTH = 24
MAX_TAGS_PER_LINK = 5
MAX_TAGS_PER_USER = 50
_BAD = re.compile(r"[<>\"'&#?/\\\x00-\x1f]")  # nothing that would confuse an address or a page


def clean_tag(raw: str) -> str:
    """One tag in its stored form: trimmed, single spaces, lower case."""
    return " ".join((raw or "").split()).lower()


def parse_tags(raw: str | None) -> list[str]:
    """'Work, school ,WORK' -> ['work', 'school']. Raises ValueError with a friendly message."""
    names: list[str] = []
    for part in re.split(r"[,\n]", raw or ""):
        name = clean_tag(part)
        if not name or name in names:
            continue
        if len(name) > MAX_TAG_LENGTH or _BAD.search(name):
            raise ValueError(
                "A tag can be up to 24 characters, without symbols like # ? / & or quotes."
            )
        names.append(name)
    if len(names) > MAX_TAGS_PER_LINK:
        raise ValueError("A link can have up to 5 tags.")
    return names


def tag_color(name: str) -> int:
    """Which of the six chart colours (1-6) a tag wears. The same name always gets the same one."""
    return int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16) % 6 + 1


def prune_tags(db: Session, user: User) -> None:
    """Forget tags that no link uses any more."""
    used = select(link_tags.c.tag_id)
    db.execute(delete(Tag).where(Tag.user_id == user.id, Tag.id.not_in(used)))


def set_link_tags(db: Session, user: User, link: Link, names: list[str]) -> None:
    """Give the link exactly these tags, creating the ones the user does not have yet."""
    have = {t.name: t for t in db.scalars(select(Tag).where(Tag.user_id == user.id))}
    fresh = [n for n in names if n not in have]
    if len(have) + len(fresh) > MAX_TAGS_PER_USER:
        raise ValueError("You can have up to 50 tags in total.")
    for name in fresh:
        have[name] = Tag(user_id=user.id, name=name)
        db.add(have[name])
    link.tags = [have[n] for n in names]
