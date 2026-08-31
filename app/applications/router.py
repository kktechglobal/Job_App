"""HTTP handlers for job applications.

Two sides, deliberately separate routes rather than one route that behaves
differently depending on who calls it: candidates apply and withdraw,
employers read the applications on their own jobs and move them along.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.applications import service
from app.applications.enums import ApplicationStatus
from app.applications.schemas import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationStatusUpdate,
)
from app.auth.dependencies import require_role
from app.database.db import get_session as get_db
from app.users.models import User, UserRole

router = APIRouter(prefix="/applications", tags=["Applications"])


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def apply(
    data: ApplicationCreate,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncSession = Depends(get_db),
):
    """Apply to a published job. One application per job; a second is a 409."""
    return await service.apply(db, current_user.id, data)


@router.get("/me", response_model=List[ApplicationResponse])
async def list_my_applications(
    status_filter: Optional[ApplicationStatus] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncSession = Depends(get_db),
):
    items, _ = await service.list_for_candidate(
        db, current_user.id, status=status_filter, limit=limit, offset=offset
    )
    return items


@router.get("/by-job/{job_id}", response_model=List[ApplicationResponse])
async def list_applications_for_job(
    job_id: int,
    status_filter: Optional[ApplicationStatus] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_role(UserRole.EMPLOYER)),
    db: AsyncSession = Depends(get_db),
):
    """Applicants for one of your jobs, best match first."""
    items, _ = await service.list_for_job(
        db, current_user.id, job_id, status=status_filter, limit=limit, offset=offset
    )
    return items


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_my_application(
    application_id: int,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_for_candidate(db, current_user.id, application_id)


@router.patch("/{application_id}/status", response_model=ApplicationResponse)
async def update_application_status(
    application_id: int,
    data: ApplicationStatusUpdate,
    current_user: User = Depends(require_role(UserRole.EMPLOYER)),
    db: AsyncSession = Depends(get_db),
):
    """Move an application along. Hired, rejected and withdrawn are final."""
    return await service.set_status(db, current_user.id, application_id, data.status)


@router.post("/{application_id}/withdraw", response_model=ApplicationResponse)
async def withdraw_application(
    application_id: int,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncSession = Depends(get_db),
):
    """The candidate's own decision. The row is kept, not deleted."""
    return await service.withdraw(db, current_user.id, application_id)
