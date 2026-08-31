"""Vacancy operations.

Visibility is the rule that shapes the reads. A job is on the public board
only when it is published by its employer, approved by an administrator, and
not yet expired. The employer's own listing ignores all three, because they
need to see their drafts.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.companies.models import EmployerProfile
from app.exceptions import (
    DuplicateResourceException,
    EntityNotFoundException,
    InvalidOperationException,
)
from app.jobs.enums import ExperienceLevel, JobLevel, JobType
from app.jobs.models import JobPost, JobPromotion
from app.jobs.schemas import JobPostCreate, JobPostUpdate, JobPromotionCreate
from app.skills.models import Skill


def _aware(value: datetime) -> datetime:
    """Compare stored timestamps safely on any backend.

    Postgres returns timezone-aware datetimes for a timestamptz column, but
    SQLite has no timezone type and hands back a naive one -- so a direct
    comparison against datetime.now(timezone.utc) raises TypeError there and
    nowhere else. Values are written as UTC, so that is what a naive one means.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


async def _employer_for_user(db: AsyncSession, user_id: int) -> EmployerProfile:
    result = await db.execute(
        select(EmployerProfile).where(EmployerProfile.user_id == user_id)
    )
    employer = result.scalars().first()
    if not employer:
        raise EntityNotFoundException(
            "Company profile not found. Please create a profile first."
        )
    return employer


async def _resolve_skills(db: AsyncSession, names: List[str]) -> List[Skill]:
    if not names:
        return []
    found = await db.execute(select(Skill).where(Skill.name.in_(names)))
    existing = {s.name: s for s in found.scalars().all()}
    for name in names:
        if name not in existing:
            skill = Skill(name=name)
            db.add(skill)
            existing[name] = skill
    await db.flush()
    return [existing[name] for name in names]


async def _owned_job(db: AsyncSession, user_id: int, job_id: int) -> JobPost:
    employer = await _employer_for_user(db, user_id)
    result = await db.execute(
        select(JobPost)
        .where(JobPost.id == job_id, JobPost.employer_id == employer.id)
        .options(selectinload(JobPost.required_skills))
    )
    job = result.scalars().first()
    if not job:
        # Same answer as a job that does not exist, so an employer cannot
        # probe for other companies' job ids.
        raise EntityNotFoundException("Job posting not found.")
    return job

# -------------------------------------------------------------- writes


async def create_job(db: AsyncSession, user_id: int, data: JobPostCreate) -> JobPost:
    employer = await _employer_for_user(db, user_id)
    values = data.model_dump(exclude={"required_skills"})

    job = JobPost(employer_id=employer.id, **values)
    job.required_skills = await _resolve_skills(db, data.required_skills)

    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def update_job(
    db: AsyncSession, user_id: int, job_id: int, data: JobPostUpdate
) -> JobPost:
    job = await _owned_job(db, user_id, job_id)
    changes = data.model_dump(exclude_unset=True)

    skills = changes.pop("required_skills", None)
    if skills is not None:
        job.required_skills = await _resolve_skills(db, skills)

    # Both halves of the range are checked together against what will
    # actually be stored, since a patch may carry only one of them.
    low: Decimal = changes.get("salary_min", job.salary_min)
    high: Decimal = changes.get("salary_max", job.salary_max)
    if low > high:
        raise InvalidOperationException("salary_min cannot be greater than salary_max.")

    if changes.get("expiration_date") is not None:
        if changes["expiration_date"] <= datetime.now(timezone.utc):
            raise InvalidOperationException("expiration_date must be in the future.")

    for field, value in changes.items():
        setattr(job, field, value)

    await db.commit()
    await db.refresh(job)
    return job


async def set_published(
    db: AsyncSession, user_id: int, job_id: int, is_published: bool
) -> JobPost:
    """Publishing is separate from editing so a half-written draft cannot
    reach the board by accident."""
    job = await _owned_job(db, user_id, job_id)

    if is_published and _aware(job.expiration_date) <= datetime.now(timezone.utc):
        raise InvalidOperationException("This posting has already expired.")

    job.is_published = is_published
    await db.commit()
    await db.refresh(job)
    return job


async def delete_job(db: AsyncSession, user_id: int, job_id: int) -> None:
    job = await _owned_job(db, user_id, job_id)
    await db.delete(job)
    await db.commit()

# --------------------------------------------------------------- reads


def _visible():
    """The three conditions that put a job on the public board."""
    return (
        JobPost.is_published.is_(True),
        JobPost.is_approved_by_admin.is_(True),
        JobPost.expiration_date > datetime.now(timezone.utc),
    )


async def search_jobs(
    db: AsyncSession,
    *,
    q: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    job_type: Optional[JobType] = None,
    job_level: Optional[JobLevel] = None,
    experience_level: Optional[ExperienceLevel] = None,
    fully_remote: Optional[bool] = None,
    salary_min: Optional[Decimal] = None,
    skill: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> Tuple[Sequence[JobPost], int]:
    filters = list(_visible())

    if q:
        pattern = f"%{q.lower()}%"
        filters.append(
            or_(
                func.lower(JobPost.title).like(pattern),
                func.lower(JobPost.job_role).like(pattern),
                func.lower(JobPost.job_description).like(pattern),
            )
        )
    if country:
        filters.append(func.lower(JobPost.country) == country.lower())
    if city:
        filters.append(func.lower(JobPost.city) == city.lower())
    if job_type is not None:
        filters.append(JobPost.job_type == job_type)
    if job_level is not None:
        filters.append(JobPost.job_level == job_level)
    if experience_level is not None:
        filters.append(JobPost.experience_level == experience_level)
    if fully_remote is not None:
        filters.append(JobPost.fully_remote.is_(fully_remote))
    if salary_min is not None:
        # "Pays at least X" means the top of the range reaches X, not the
        # bottom -- otherwise a 90k-150k job is hidden from a 100k search.
        filters.append(JobPost.salary_max >= salary_min)

    query = select(JobPost).where(*filters)
    count_query = select(func.count()).select_from(JobPost).where(*filters)
    if skill:
        joined = JobPost.required_skills.any(Skill.name == skill.strip().lower())
        query = query.where(joined)
        count_query = count_query.where(joined)

    total = await db.execute(count_query)
    rows = await db.execute(
        query.options(selectinload(JobPost.required_skills))
        .order_by(JobPost.created_at.desc(), JobPost.id.desc())
        .limit(limit).offset(offset)
    )
    return rows.scalars().all(), total.scalar_one()


async def get_job_public(db: AsyncSession, job_id: int) -> JobPost:
    result = await db.execute(
        select(JobPost)
        .where(JobPost.id == job_id, *_visible())
        .options(selectinload(JobPost.required_skills))
    )
    job = result.scalars().first()
    if not job:
        raise EntityNotFoundException("Job posting not found.")
    return job


async def list_mine(
    db: AsyncSession, user_id: int, *, is_published: Optional[bool] = None,
    limit: int = 50, offset: int = 0,
) -> Tuple[Sequence[JobPost], int]:
    """Drafts and expired postings included -- this is the employer's own
    list, not the public board."""
    employer = await _employer_for_user(db, user_id)
    filters = [JobPost.employer_id == employer.id]
    if is_published is not None:
        filters.append(JobPost.is_published.is_(is_published))

    total = await db.execute(select(func.count()).select_from(JobPost).where(*filters))
    rows = await db.execute(
        select(JobPost).where(*filters)
        .options(selectinload(JobPost.required_skills))
        .order_by(JobPost.created_at.desc(), JobPost.id.desc())
        .limit(limit).offset(offset)
    )
    return rows.scalars().all(), total.scalar_one()


async def get_mine(db: AsyncSession, user_id: int, job_id: int) -> JobPost:
    return await _owned_job(db, user_id, job_id)

# ---------------------------------------------------------- promotions


async def promote_job(
    db: AsyncSession, user_id: int, job_id: int, data: JobPromotionCreate
) -> JobPromotion:
    job = await _owned_job(db, user_id, job_id)

    if data.featured_until is not None:
        if data.featured_until.tzinfo is None:
            raise InvalidOperationException("featured_until must include a timezone offset.")
        if data.featured_until <= datetime.now(timezone.utc):
            raise InvalidOperationException("featured_until must be in the future.")

    promotion = JobPromotion(job_id=job.id, **data.model_dump())
    db.add(promotion)
    try:
        await db.commit()
    except IntegrityError as exc:
        # payment_reference is unique: the same payment must not be able to
        # buy two promotions.
        await db.rollback()
        raise DuplicateResourceException(
            "That payment reference has already been used."
        ) from exc

    await db.refresh(promotion)
    return promotion


async def list_promotions(
    db: AsyncSession, user_id: int, job_id: int
) -> Sequence[JobPromotion]:
    job = await _owned_job(db, user_id, job_id)
    result = await db.execute(
        select(JobPromotion)
        .where(JobPromotion.job_id == job.id)
        .order_by(JobPromotion.created_at.desc())
    )
    return result.scalars().all()
