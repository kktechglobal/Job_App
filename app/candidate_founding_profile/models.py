from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.skills.models import candidate_skills

if TYPE_CHECKING:
    from app.application.models import Application
    from app.skills.models import Skill
    from app.users.models import User


class CandidateProfile(Base):
    """A job seeker. One per CANDIDATE user."""

    __tablename__ = "candidate_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    headline: Mapped[Optional[str]] = mapped_column(String(200))
    bio: Mapped[Optional[str]] = mapped_column(Text)
    resume_url: Mapped[Optional[str]] = mapped_column(String(500))
    years_experience: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    phone_number: Mapped[Optional[str]] = mapped_column(String(30))
    country: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), index=True)

    user: Mapped["User"] = relationship(back_populates="profile", lazy="selectin")
    applications: Mapped[List["Application"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True
    )
    skills: Mapped[List["Skill"]] = relationship(
        secondary=candidate_skills, back_populates="candidates", lazy="selectin"
    )
