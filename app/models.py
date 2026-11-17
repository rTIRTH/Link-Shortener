from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, deferred, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    avatar: Mapped[str] = mapped_column(String(32), default="cat", server_default="cat")
    theme: Mapped[str] = mapped_column(String(8), default="system", server_default="system")
    language: Mapped[str] = mapped_column(String(5), default="en", server_default="en")
    # When the profile photo was last set (None = using one of the animal avatars)
    photo_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # When the email address was confirmed with a code (None = never confirmed)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    links: Mapped[list["Link"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    tags: Mapped[list["Tag"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", order_by="Tag.name"
    )
    old_usernames: Mapped[list["UsernameAlias"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    photo: Mapped["ProfilePhoto | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    email_change: Mapped["EmailChange | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )


# Which tags a link has (a link can have a few; a tag can be on many links).
link_tags = Table(
    "link_tags",
    Base.metadata,
    Column("link_id", ForeignKey("links.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


class Tag(Base):
    """A label the owner puts on links to group them. Names are lower case and unique per user."""

    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_tags_user_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(24))

    owner: Mapped["User"] = relationship(back_populates="tags")
    links: Mapped[list["Link"]] = relationship(secondary=link_tags, back_populates="tags")


class Link(Base):
    __tablename__ = "links"
    # The "namespace": a slug only has to be unique per user.
    __table_args__ = (UniqueConstraint("user_id", "slug", name="uq_links_user_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    slug: Mapped[str] = mapped_column(String(32))
    original_url: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    click_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # The owner's on/off switch. Off = visitors see a message, whatever the schedule says.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    # The link stops working once it has had this many clicks (None = no limit).
    click_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # When the last click of the limit was used (None until then, and again if the limit changes).
    limit_reached_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Optional page shown before the redirect ("You're going to example.com"), with a message.
    preview: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    preview_message: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # QR code style: colours (#rrggbb) and a small PNG logo for the centre. None = the default.
    qr_fg: Mapped[str | None] = mapped_column(String(7), nullable=True)
    qr_bg: Mapped[str | None] = mapped_column(String(7), nullable=True)
    qr_logo: Mapped[bytes | None] = deferred(mapped_column(LargeBinary, nullable=True))
    # Archived links are hidden from the dashboard list but keep working and keep their stats.
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped[User] = relationship(back_populates="links")
    tags: Mapped[list[Tag]] = relationship(
        secondary=link_tags, back_populates="links", order_by="Tag.name"
    )
    clicks: Mapped[list["Click"]] = relationship(
        back_populates="link", cascade="all, delete-orphan"
    )
    toggles: Mapped[list["LinkToggle"]] = relationship(
        back_populates="link", cascade="all, delete-orphan", order_by="LinkToggle.at"
    )
    edits: Mapped[list["LinkEdit"]] = relationship(
        back_populates="link", cascade="all, delete-orphan", order_by="LinkEdit.at"
    )


class Click(Base):
    __tablename__ = "clicks"

    id: Mapped[int] = mapped_column(primary_key=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("links.id"), index=True)
    clicked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    device: Mapped[str] = mapped_column(String(16), default="desktop")
    referrer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Who clicked (all optional: clicks from before these columns existed have none of them).
    source: Mapped[str | None] = mapped_column(String(24), nullable=True)  # whatsapp, direct, ...
    browser: Mapped[str | None] = mapped_column(String(16), nullable=True)
    os: Mapped[str | None] = mapped_column(String(16), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)  # ISO code, e.g. IN
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    visitor: Mapped[str | None] = mapped_column(String(16), nullable=True)  # salted hash, no IP

    link: Mapped[Link] = relationship(back_populates="clicks")


class LinkToggle(Base):
    """One time the owner switched a link off or on: the history behind the activity log."""

    __tablename__ = "link_toggles"

    id: Mapped[int] = mapped_column(primary_key=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("links.id"), index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    active: Mapped[bool] = mapped_column(Boolean)  # the state it was switched TO

    link: Mapped[Link] = relationship(back_populates="toggles")


class LinkEdit(Base):
    """One time the owner pointed a link at a new destination (the short address never changes)."""

    __tablename__ = "link_edits"

    id: Mapped[int] = mapped_column(primary_key=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("links.id"), index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    old_url: Mapped[str] = mapped_column(Text)
    new_url: Mapped[str] = mapped_column(Text)

    link: Mapped[Link] = relationship(back_populates="edits")


class UsernameAlias(Base):
    """A previous username. It keeps old short links working and stays reserved."""

    __tablename__ = "username_aliases"

    username: Mapped[str] = mapped_column(String(20), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="old_usernames")


class EmailChange(Base):
    """A pending email change waiting for the one-time code (max one per user)."""

    __tablename__ = "email_changes"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    new_email: Mapped[str] = mapped_column(String(255))
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped[User] = relationship(back_populates="email_change")


class PendingSignup(Base):
    """A sign-up waiting for its emailed code. No account (and no username) exists until then."""

    __tablename__ = "pending_signups"

    email: Mapped[str] = mapped_column(String(255), primary_key=True)
    username: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(5), default="en")
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProfilePhoto(Base):
    """A person's own profile picture (256x256 JPEG), kept in the database."""

    __tablename__ = "profile_photos"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="photo")
