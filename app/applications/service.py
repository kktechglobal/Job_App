"""Applying to jobs, and moving an application through its statuses.

Ownership is a join in both directions. A candidate reaches their own
applications through CandidateProfile; an employer reaches the ones on their
jobs through JobPost. Neither can name an id belonging to the other.
"""

from typing import Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.matching import service as matching_service
from app.applications.enums import ApplicationStatus
from app.applications.models import Application
from app.applications.schemas import ApplicationCreate
from app.candidates.models import CandidateProfile
from app.companies.models import EmployerProfile
from app.exceptions import (
    DuplicateResourceException,
    EntityNotFoundException,
    InvalidOperationException,
)
from app.jobs.models import JobPost

# Once one of these is reached the application is finished; a status change
# out of it would rewrite a decision that has already been communicated.
TERMINAL = {ApplicationStatus.HIRED, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN}


async def _candidate_for_user(db: AsyncSession, user_id: int) -> CandidateProfile:
    result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == user_id)
    )
    profile = result.scalars().first()
    if not profile:
        raise EntityNotFoundException(
            "Candidate profile not found. Please create a profile first."
        )
    return profile


async def apply(
    db: AsyncSession, user_id: int, data: ApplicationCreate
) -> Application:
    candidate = await _candidate_for_user(db, user_id)

    job = (await db.execute(
        select(JobPost)
        .where(JobPost.id == data.job_id)
        .options(selectinload(JobPost.required_skills))
    )).scalars().first()
    if not job:
        raise EntityNotFoundException("Job posting not found.")

    # A draft or unapproved posting is not open for applications, and
    # saying so is better than accepting one that nobody will read.
    if not job.is_published or not job.is_approved_by_admin:
        raise InvalidOperationException("This job is not open for applications.")

    application = Application(
        job_id=job.id,
        candidate_id=candidate.id,
        cover_letter=data.cover_letter,
        match_score=matching_service.score(candidate.skills, job.required_skills),
        status=ApplicationStatus.SUBMITTED,
    )
    db.add(application)
    try:
        await db.commit()
    except IntegrityError as exc:
        # uq_application_job_candidate. Two simultaneous requests both read
        # "not applied yet" and both insert; only the database settles it.
        await db.rollback()
        raise DuplicateResourceException("You have already applied to this job.") from exc

    await db.refresh(application)
    return application


async def list_for_candidate(
    db: AsyncSession, user_id: int, *, status: Optional[ApplicationStatus] = None,
    limit: int = 50, offset: int = 0,
) -> Tuple[Sequence[Application], int]:
    candidate = await _candidate_for_user(db, user_id)
    filters = [Application.candidate_id == candidate.id]
    if status is not None:
        filters.append(Application.status == status)

    total = await db.execute(select(func.count()).select_from(Application).where(*filters))
    rows = await db.execute(
        select(Application).where(*filters)
        .order_by(Application.submitted_at.desc()).limit(limit).offset(offset)
    )
    return rows.scalars().all(), total.scalar_one()


async def list_for_job(
    db: AsyncSession, user_id: int, job_id: int, *,
    status: Optional[ApplicationStatus] = None, limit: int = 50, offset: int = 0,
) -> Tuple[Sequence[Application], int]:
    owned = await db.execute(
        select(JobPost.id)
        .join(EmployerProfile, JobPost.employer_id == EmployerProfile.id)
        .where(JobPost.id == job_id, EmployerProfile.user_id == user_id)
    )
    if not owned.first():
        # Same answer as a job that does not exist, so an employer cannot
        # probe for other companies' job ids.
        raise EntityNotFoundException("Job posting not found.")

    filters = [Application.job_id == job_id]
    if status is not None:
        filters.append(Application.status == status)

    total = await db.execute(select(func.count()).select_from(Application).where(*filters))
    rows = await db.execute(
        select(Application).where(*filters)
        .order_by(Application.match_score.desc(), Application.submitted_at)
        .limit(limit).offset(offset)
    )
    return rows.scalars().all(), total.scalar_one()


async def get_for_candidate(db: AsyncSession, user_id: int, application_id: int) -> Application:
    result = await db.execute(
        select(Application)
        .join(CandidateProfile, Application.candidate_id == CandidateProfile.id)
        .where(Application.id == application_id, CandidateProfile.user_id == user_id)
    )
    application = result.scalars().first()
    if not application:
        raise EntityNotFoundException("Application not found.")
    return application


async def get_for_employer(db: AsyncSession, user_id: int, application_id: int) -> Application:
    result = await db.execute(
        select(Application)
        .join(JobPost, Application.job_id == JobPost.id)
        .join(EmployerProfile, JobPost.employer_id == EmployerProfile.id)
        .where(Application.id == application_id, EmployerProfile.user_id == user_id)
    )
    application = result.scalars().first()
    if not application:
        raise EntityNotFoundException("Application not found.")
    return application


async def set_status(
    db: AsyncSession, user_id: int, application_id: int, status: ApplicationStatus
) -> Application:
    application = await get_for_employer(db, user_id, application_id)

    if application.status in TERMINAL:
        raise InvalidOperationException(
            f"This application is already {application.status.value} and cannot be changed."
        )
    # Withdrawing is the candidate's decision, not the employer's.
    if status == ApplicationStatus.WITHDRAWN:
        raise InvalidOperationException("Only the candidate can withdraw an application.")

    application.status = status
    await db.commit()
    await db.refresh(application)
    return application


async def withdraw(db: AsyncSession, user_id: int, application_id: int) -> Application:
    application = await get_for_candidate(db, user_id, application_id)

    if application.status in TERMINAL:
        raise InvalidOperationException(
            f"This application is already {application.status.value}."
        )

    # Kept rather than deleted: the unique constraint then stops someone
    # re-applying to a job they withdrew from, and the employer's records
    # do not lose a row they have already seen.
    application.status = ApplicationStatus.WITHDRAWN
    await db.commit()
    await db.refresh(application)
    return application
