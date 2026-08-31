"""Skills, and the two association tables that link them to candidates and jobs.

A join table rather than a text column because match_score compares a
candidate's skills against a job's requirements -- that only works when both
sides point at the same skill rows.
"""

from typing import List, TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.candidates.models import CandidateProfile
    from app.jobs.models import JobPost


candidate_skills = Table(
    "candidate_skills",
    Base.metadata,
    Column("candidate_id", ForeignKey("candidate_profiles.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)

job_required_skills = Table(
    "job_required_skills",
    Base.metadata,
    Column("job_id", ForeignKey("job_posts.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Normalise to lowercase in the service before inserting, or "Python" and
    # "python" become two skills and matching silently stops working.
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)

    candidates: Mapped[List["CandidateProfile"]] = relationship(
        secondary=candidate_skills, back_populates="skills"
    )
    jobs: Mapped[List["JobPost"]] = relationship(
        secondary=job_required_skills, back_populates="required_skills"
    )
