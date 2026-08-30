from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.users.enums import UserRole  # re-exported: app.core.dependencies imports it from here

if TYPE_CHECKING:
    from app.candidate_founding_profile.models import CandidateProfile
    from app.employer_profile.models import EmployerProfile


class User(Base):
    """Anyone who logs in. `role` decides which kind of account it is."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
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
