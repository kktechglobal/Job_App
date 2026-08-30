from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    
    # Profile Details
    headline: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # e.g. "Senior Python Developer"
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resume_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    
    # Skills & Experience
    skills: Mapped[List[str]] = mapped_column(ARRAY(String), default=[], nullable=False)
    years_experience: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expected_salary_min: Mapped[Optional[float]] = mapped_column(nullable=True)
    expected_salary_max: Mapped[Optional[float]] = mapped_column(nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_open_to_relocation: Mapped[bool] = mapped_column(default=False)
    is_open_to_remote: Mapped[bool] = mapped_column(default=True)

    # Metrics
    completeness_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="profile")
    applications: Mapped[List["Application"]] = relationship("Application", back_populates="candidate", cascade="all, delete-orphan")
    funding_profile: Mapped[Optional["CandidateFundingProfile"]] = relationship("CandidateFundingProfile", back_populates="candidate", uselist=False, cascade="all, delete-orphan")
    saved_cards: Mapped[List["SavedCandidateCard"]] = relationship("SavedCandidateCard", back_populates="candidate", cascade="all, delete-orphan")