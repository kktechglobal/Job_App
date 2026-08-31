"""HTTP surface for interviews.

Identity comes from the authenticated user, never a request header -- a
caller must not be able to book an interview on someone else's application.

Booking, rescheduling and cancelling are the employer's. Reading is shared:
GET /interviews/me is the candidate's list, and GET /interviews/{id} resolves
for whichever side is asking.
"""

from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.database.db import get_session as get_db
from app.interviews import service
from app.interviews.schemas import InterviewCreate, InterviewResponse, InterviewUpdate
from app.users.models import User, UserRole

router = APIRouter(prefix="/interviews", tags=["Interviews"])


@router.post("", response_model=InterviewResponse, status_code=status.HTTP_201_CREATED)
async def book_interview(
    data: InterviewCreate,
    current_user: User = Depends(require_role(UserRole.EMPLOYER)),
    db: AsyncSession = Depends(get_db),
):
    """Book an interview on one of your own applications. One per
    application; a second booking is a 409."""
    return await service.book(db, current_user.id, data)


# Declared before "/{interview_id}" so the literal paths win.
@router.get("/me", response_model=List[InterviewResponse])
async def list_my_interviews(
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncSession = Depends(get_db),
):
    """The candidate's own interviews, soonest first."""
    return await service.list_for_candidate(db, current_user.id)


@router.get("/by-application/{application_id}", response_model=InterviewResponse)
async def get_interview_for_application(
    application_id: int,
    current_user: User = Depends(require_role(UserRole.EMPLOYER)),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_for_application(db, current_user.id, application_id)


@router.get("/{interview_id}", response_model=InterviewResponse)
async def get_interview(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Readable by the employer who booked it or the candidate attending it.
    Anyone else gets a 404, not a 403 -- an interview id should not be
    confirmable by a stranger."""
    return await service.get_for_viewer(db, current_user, interview_id)


@router.patch("/{interview_id}", response_model=InterviewResponse)
async def reschedule_interview(
    interview_id: int,
    data: InterviewUpdate,
    current_user: User = Depends(require_role(UserRole.EMPLOYER)),
    db: AsyncSession = Depends(get_db),
):
    """Change the time, the link or the notes. The new time must be in the future."""
    return await service.update_interview(db, current_user.id, interview_id, data)


@router.delete("/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_interview(
    interview_id: int,
    current_user: User = Depends(require_role(UserRole.EMPLOYER)),
    db: AsyncSession = Depends(get_db),
):
    await service.cancel(db, current_user.id, interview_id)
