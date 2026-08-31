"""Request/response shapes for vacancies.

`is_published` and `is_approved_by_admin` are absent from the write schemas.
Publishing is its own endpoint, and approval belongs to app/admin/ -- an
employer must not be able to approve their own posting by sending a flag.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.jobs.enums import (
    Currency, ExperienceLevel, JobLevel, JobType, PromotionPlan, SalaryType,
)


class JobPostCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    job_role: str = Field(..., min_length=1, max_length=200)
    job_description: str = Field(..., min_length=1)

    salary_min: Decimal = Field(..., ge=0, max_digits=12, decimal_places=2)
    salary_max: Decimal = Field(..., ge=0, max_digits=12, decimal_places=2)
    currency: Currency = Currency.NGN
    salary_type: SalaryType

    job_level: JobLevel
    experience_level: ExperienceLevel
    job_type: JobType

    vacancies: int = Field(..., ge=1)
    expiration_date: datetime

    fully_remote: bool = False
    country: str = Field(..., min_length=1, max_length=200)
    city: str = Field(..., min_length=1, max_length=200)

    job_benefits: List[str] = Field(default_factory=list, max_length=50)
    required_skills: List[str] = Field(default_factory=list, max_length=50)

    @field_validator("required_skills")
    @classmethod
    def _normalise(cls, values: List[str]) -> List[str]:
        # The Skill table is unique on name, so "Python" and "python" would
        # otherwise become two rows and matching would quietly stop working.
        cleaned = [v.strip().lower() for v in values if v and v.strip()]
        return list(dict.fromkeys(cleaned))

    @field_validator("expiration_date")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expiration_date must include a timezone offset")
        return value

    @model_validator(mode="after")
    def _coherent(self) -> "JobPostCreate":
        # Mirrors ck_job_posts_salary_range, so this is a 422 rather than a 500
        # from the database.
        if self.salary_min > self.salary_max:
            raise ValueError("salary_min cannot be greater than salary_max")
        if self.expiration_date <= datetime.now(timezone.utc):
            raise ValueError("expiration_date must be in the future")
        return self


class JobPostUpdate(BaseModel):
    """Only the supplied fields change. Sending `required_skills` replaces the
    whole set. Salary and expiry are revalidated in the service against the
    values already stored."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    job_role: Optional[str] = Field(default=None, min_length=1, max_length=200)
    job_description: Optional[str] = Field(default=None, min_length=1)

    salary_min: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    salary_max: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: Optional[Currency] = None
    salary_type: Optional[SalaryType] = None

    job_level: Optional[JobLevel] = None
    experience_level: Optional[ExperienceLevel] = None
    job_type: Optional[JobType] = None

    vacancies: Optional[int] = Field(default=None, ge=1)
    expiration_date: Optional[datetime] = None

    fully_remote: Optional[bool] = None
    country: Optional[str] = Field(default=None, min_length=1, max_length=200)
    city: Optional[str] = Field(default=None, min_length=1, max_length=200)

    job_benefits: Optional[List[str]] = Field(default=None, max_length=50)
    required_skills: Optional[List[str]] = Field(default=None, max_length=50)

    @field_validator("required_skills")
    @classmethod
    def _normalise(cls, values: Optional[List[str]]) -> Optional[List[str]]:
        if values is None:
            return None
        cleaned = [v.strip().lower() for v in values if v and v.strip()]
        return list(dict.fromkeys(cleaned))

    @field_validator("expiration_date")
    @classmethod
    def _aware(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("expiration_date must include a timezone offset")
        return value


class JobPostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employer_id: int
    title: str
    job_role: str
    job_description: str

    salary_min: Decimal
    salary_max: Decimal
    currency: Currency
    salary_type: SalaryType

    job_level: JobLevel
    experience_level: ExperienceLevel
    job_type: JobType

    vacancies: int
    expiration_date: datetime

    fully_remote: bool
    country: str
    city: str

    job_benefits: List[str] = Field(default_factory=list)
    required_skills: List[str] = Field(default_factory=list)

    is_published: bool
    is_approved_by_admin: bool
    created_at: datetime

    @field_validator("required_skills", mode="before")
    @classmethod
    def _skill_names(cls, value):
        # Arrives as a list of Skill rows when read off the ORM object.
        return [s.name if hasattr(s, "name") else s for s in value or []]


class JobPromotionCreate(BaseModel):
    plan: PromotionPlan
    featured_until: Optional[datetime] = None
    amount_paid: Decimal = Field(..., ge=0, max_digits=12, decimal_places=2)
    currency: Currency = Currency.NGN
    payment_reference: str = Field(..., min_length=1, max_length=120)


class JobPromotionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    plan: PromotionPlan
    featured_until: Optional[datetime]
    amount_paid: Decimal
    currency: Currency
    payment_reference: str
    created_at: datetime
