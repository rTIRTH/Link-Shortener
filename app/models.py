from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    links: Mapped[list["Link"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    old_usernames: Mapped[list["UsernameAlias"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    email_change: Mapped["EmailChange | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )


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

    owner: Mapped[User] = relationship(back_populates="links")
    clicks: Mapped[list["Click"]] = relationship(
        back_populates="link", cascade="all, delete-orphan"
    )


class Click(Base):
    __tablename__ = "clicks"

    id: Mapped[int] = mapped_column(primary_key=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("links.id"), index=True)
    clicked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    device: Mapped[str] = mapped_column(String(16), default="desktop")
    referrer: Mapped[str | None] = mapped_column(String(255), nullable=True)

    link: Mapped[Link] = relationship(back_populates="clicks")


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
