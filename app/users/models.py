"""Accounts, and the preferences attached to them."""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.users.enums import UserRole  # re-exported: app.auth.dependencies imports it from here

if TYPE_CHECKING:
    from app.candidates.models import CandidateProfile
    from app.companies.models import EmployerProfile


class User(Base):
    """Anyone who logs in. `role` decides which kind of account it is."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    # Stored lowercased and unique. It is a public handle -- it can appear in a
    # profile URL -- so "Danny" and "danny" must not be two different people.
    username: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)  # bcrypt is 60 chars
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)

    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", native_enum=False, length=20),
        default=UserRole.CANDIDATE,
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Bumped on logout and on password change. Every access token carries the
    # value it was minted with, so raising this invalidates tokens already in
    # the wild -- which a stateless JWT otherwise cannot do.
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # When the terms were accepted, not whether. A boolean cannot answer
    # "which version did they agree to, and when" -- which is the only reason
    # to record consent at all.
    accepted_terms_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    profile: Mapped[Optional["CandidateProfile"]] = relationship(
        back_populates="user", lazy="selectin",
        cascade="all, delete-orphan", passive_deletes=True,
    )
    employer_profile: Mapped[Optional["EmployerProfile"]] = relationship(
        back_populates="user", lazy="selectin",
        cascade="all, delete-orphan", passive_deletes=True,
    )
    settings: Mapped[Optional["AccountSetting"]] = relationship(
        back_populates="user", lazy="selectin",
        cascade="all, delete-orphan", passive_deletes=True,
    )


class AccountSetting(Base):
    """Notification and privacy preferences. One per user."""

    __tablename__ = "account_information"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    job_alert_emails: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    profile_is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship(back_populates="settings", lazy="selectin")
