"""Interview operations.

Ownership runs Interview -> Application -> JobPost -> EmployerProfile. An
employer may only touch interviews on their own job posts; a candidate may
only read interviews on their own applications. Both checks are joins, not
trust in a request header.
"""

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.applications.models import Application
from app.candidates.models import CandidateProfile
from app.exceptions import (
    DuplicateResourceException,
    EntityNotFoundException,
    InvalidOperationException,
)
from app.companies.models import EmployerProfile
from app.interviews.models import Interview
from app.interviews.schemas import InterviewCreate, InterviewUpdate
from app.jobs.models import JobPost
from app.users.models import User, UserRole


# ------------------------------------------------------------ lookups


async def _employer_application(
    db: AsyncSession, user_id: int, application_id: int
) -> Application:
    """The application, but only if it is on one of this employer's jobs."""
    result = await db.execute(
        select(Application)
        .join(JobPost, Application.job_id == JobPost.id)
        .join(EmployerProfile, JobPost.employer_id == EmployerProfile.id)
        .where(
            Application.id == application_id,
            EmployerProfile.user_id == user_id,
        )
    )
    application = result.scalars().first()
    if not application:
        # Deliberately the same answer as "does not exist": an employer
        # must not be able to probe for other people's application ids.
        raise EntityNotFoundException("Application not found.")
    return application


async def _owned_interview(db: AsyncSession, user_id: int, interview_id: int) -> Interview:
    result = await db.execute(
        select(Interview)
        .join(Application, Interview.application_id == Application.id)
        .join(JobPost, Application.job_id == JobPost.id)
        .join(EmployerProfile, JobPost.employer_id == EmployerProfile.id)
        .where(Interview.id == interview_id, EmployerProfile.user_id == user_id)
    )
    interview = result.scalars().first()
    if not interview:
        raise EntityNotFoundException("Interview not found.")
    return interview

# ------------------------------------------------------------- writes


async def book(db: AsyncSession, user_id: int, data: InterviewCreate) -> Interview:
    await _employer_application(db, user_id, data.application_id)

    interview = Interview(**data.model_dump())
    db.add(interview)
    try:
        await db.commit()
    except IntegrityError as exc:
        # application_id is unique: one interview per application.
        await db.rollback()
        raise DuplicateResourceException(
            "An interview is already booked for this application."
        ) from exc

    await db.refresh(interview)
    return interview


async def update_interview(
    db: AsyncSession, user_id: int, interview_id: int, data: InterviewUpdate
) -> Interview:
    interview = await _owned_interview(db, user_id, interview_id)
    changes = data.model_dump(exclude_unset=True)

    # Checked here rather than in the schema: a partial update only carries
    # the new time, so the rule needs the stored value to compare against.
    if changes.get("scheduled_time") is not None:
        if changes["scheduled_time"] <= datetime.now(timezone.utc):
            raise InvalidOperationException("scheduled_time must be in the future.")

    for field, value in changes.items():
        setattr(interview, field, value)

    await db.commit()
    await db.refresh(interview)
    return interview


async def cancel(db: AsyncSession, user_id: int, interview_id: int) -> None:
    interview = await _owned_interview(db, user_id, interview_id)
    await db.delete(interview)
    await db.commit()

# -------------------------------------------------------------- reads


async def get_for_application(
    db: AsyncSession, user_id: int, application_id: int
) -> Interview:
    await _employer_application(db, user_id, application_id)
    result = await db.execute(
        select(Interview).where(Interview.application_id == application_id)
    )
    interview = result.scalars().first()
    if not interview:
        raise EntityNotFoundException("No interview is booked for this application.")
    return interview


async def list_for_candidate(db: AsyncSession, user_id: int) -> Sequence[Interview]:
    """Every interview booked against this candidate's applications."""
    result = await db.execute(
        select(Interview)
        .join(Application, Interview.application_id == Application.id)
        .join(CandidateProfile, Application.candidate_id == CandidateProfile.id)
        .where(CandidateProfile.user_id == user_id)
        .order_by(Interview.scheduled_time)
    )
    return result.scalars().all()


async def get_for_viewer(db: AsyncSession, user: User, interview_id: int) -> Interview:
    """One interview, readable by the employer who booked it or the
    candidate being interviewed."""
    if user.role == UserRole.EMPLOYER:
        return await _owned_interview(db, user.id, interview_id)

    result = await db.execute(
        select(Interview)
        .join(Application, Interview.application_id == Application.id)
        .join(CandidateProfile, Application.candidate_id == CandidateProfile.id)
        .where(Interview.id == interview_id, CandidateProfile.user_id == user.id)
    )
    interview = result.scalars().first()
    if not interview:
        raise EntityNotFoundException("Interview not found.")
    return interview
