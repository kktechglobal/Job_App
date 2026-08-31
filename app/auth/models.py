"""Refresh and password-reset tokens: revocable, single-use, expiring --
properties a stateless JWT doesn't have, which is why they need storage.

Neither table stores the raw token, only its SHA-256 digest, so a database
leak yields no usable credentials.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.users.models import User


class RefreshToken(Base):
    """One row per issued refresh token, rotated on every use: each refresh
    mints a new token and marks the old one used, so a stolen token is good
    for one call. If the *old* token is presented again, that's proof of
    theft -- the legitimate client has already moved on -- and `replaced_by`
    lets that detection revoke the whole chain."""

    __tablename__ = "refresh_tokens"

    __table_args__ = (
        Index("ix_refresh_tokens_user_active", "user_id", "revoked_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    replaced_by: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(lazy="selectin")


class PasswordResetToken(Base):
    """Single-use, short-lived, and never reissued to confirm an email exists."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(lazy="selectin")
