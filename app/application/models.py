from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.application.enums import ApplicationStatus
from app.database.base import Base

if TYPE_CHECKING:
    from app.candidate_founding_profile.models import CandidateProfile
    from app.interview.models import Interview
    from app.job_post.models import JobPost


class Application(Base):
    """One candidate applying to one job."""

    __tablename__ = "applications"

    __table_args__ = (
        # Enforced here, not in the service: two simultaneous requests both read
        # "not applied yet" and both insert. Only the database settles a race.
        UniqueConstraint("job_id", "candidate_id", name="uq_application_job_candidate"),
        CheckConstraint("match_score BETWEEN 0 AND 100", name="ck_application_match_score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("job_posts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )

    status: Mapped[ApplicationStatus] = mapped_column(
        SAEnum(ApplicationStatus, name="application_status", native_enum=False, length=30),
        default=ApplicationStatus.SUBMITTED,
        nullable=False,
        index=True,
    )
    cover_letter: Mapped[Optional[str]] = mapped_column(Text)
    match_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    job: Mapped["JobPost"] = relationship(back_populates="applications", lazy="selectin")
    candidate: Mapped["CandidateProfile"] = relationship(
        back_populates="applications", lazy="selectin"
    )
    interview: Mapped[Optional["Interview"]] = relationship(
        back_populates="application", lazy="selectin",
        cascade="all, delete-orphan", passive_deletes=True,
    )
