"""Vacancies, and the paid promotions attached to them."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.jobs.enums import (
    Currency, ExperienceLevel, JobLevel, JobType, PromotionPlan, SalaryType,
)
from app.skills.models import job_required_skills

if TYPE_CHECKING:
    from app.applications.models import Application
    from app.companies.models import EmployerProfile
    from app.skills.models import Skill


class JobPost(Base):
    """A vacancy published by an employer."""

    __tablename__ = "job_posts"

    __table_args__ = (
        CheckConstraint("salary_min <= salary_max", name="ck_job_posts_salary_range"),
        CheckConstraint("vacancies > 0", name="ck_job_posts_vacancies_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employer_id: Mapped[int] = mapped_column(
        ForeignKey("employer_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )

    title: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    job_role: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    job_description: Mapped[str] = mapped_column(Text, nullable=False)

    salary_min: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    salary_max: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[Currency] = mapped_column(
        SAEnum(Currency, name="currency", native_enum=False, length=3),
        default=Currency.NGN, nullable=False,
    )
    salary_type: Mapped[SalaryType] = mapped_column(
        SAEnum(SalaryType, name="salary_type", native_enum=False, length=20), nullable=False
    )

    job_level: Mapped[JobLevel] = mapped_column(
        SAEnum(JobLevel, name="job_level", native_enum=False, length=20), nullable=False, index=True
    )
    experience_level: Mapped[ExperienceLevel] = mapped_column(
        SAEnum(ExperienceLevel, name="experience_level", native_enum=False, length=20), nullable=False
    )
    job_type: Mapped[JobType] = mapped_column(
        SAEnum(JobType, name="job_type", native_enum=False, length=20), nullable=False, index=True
    )

    vacancies: Mapped[int] = mapped_column(Integer, nullable=False)
    expiration_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )

    fully_remote: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    country: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(200), nullable=False)

    # Benefits are only ever displayed, so JSON is enough. Skills are queried
    # and matched against candidates, so they get a join table instead.
    job_benefits: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_approved_by_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    required_skills: Mapped[List["Skill"]] = relationship(
        secondary=job_required_skills, back_populates="jobs", lazy="selectin"
    )
    employer: Mapped["EmployerProfile"] = relationship(back_populates="jobs", lazy="selectin")
    applications: Mapped[List["Application"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )
    promotions: Mapped[List["JobPromotion"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )


class JobPromotion(Base):
    """A paid promotion for one job."""

    __tablename__ = "job_promotions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("job_posts.id", ondelete="CASCADE"), index=True, nullable=False
    )

    plan: Mapped[PromotionPlan] = mapped_column(
        SAEnum(PromotionPlan, name="promotion_plan", native_enum=False, length=20), nullable=False
    )
    # Ask `featured_until > now()` rather than storing a flag -- a date expires
    # on its own, a boolean waits for someone to remember to unset it.
    featured_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)

    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[Currency] = mapped_column(
        SAEnum(Currency, name="currency", native_enum=False, length=3),
        default=Currency.NGN, nullable=False,
    )
    payment_reference: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped["JobPost"] = relationship(back_populates="promotions", lazy="selectin")
