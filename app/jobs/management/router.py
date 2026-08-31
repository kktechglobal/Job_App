"""An employer's own postings.

The other side of app/jobs/board/: this one ignores the board's visibility
rules, because an employer has to be able to see a draft in order to finish
it, and an expired posting in order to repost it.

The EMPLOYER gate is declared once on the router rather than repeated on each
handler, so a route added later inherits it instead of relying on memory.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database.db import get_session as get_db
from app.jobs import service
from app.jobs.schemas import (
    JobPostCreate,
    JobPostResponse,
    JobPostUpdate,
    JobPromotionCreate,
    JobPromotionResponse,
)
from app.users.models import User, UserRole

router = APIRouter(
    prefix="/my-jobs", tags=["My Jobs"],
    dependencies=[Depends(require_role(UserRole.EMPLOYER))],
)


def _employer(current_user: User = Depends(require_role(UserRole.EMPLOYER))) -> User:
    """The router-level dependency enforces the gate; this one hands the
    handler the employer's identity so it can scope the query."""
    return current_user


@router.post("", response_model=JobPostResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    data: JobPostCreate,
    current_user: User = Depends(_employer),
    db: AsyncSession = Depends(get_db),
):
    """Creates a draft. It reaches the board once you publish it and an
    administrator approves it."""
    return await service.create_job(db, current_user.id, data)


@router.get("", response_model=List[JobPostResponse])
async def list_my_jobs(
    is_published: Optional[bool] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(_employer),
    db: AsyncSession = Depends(get_db),
):
    """Your postings, drafts and expired ones included."""
    items, _ = await service.list_mine(
        db, current_user.id, is_published=is_published, limit=limit, offset=offset
    )
    return items


@router.get("/{job_id}", response_model=JobPostResponse)
async def get_my_job(
    job_id: int,
    current_user: User = Depends(_employer),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_mine(db, current_user.id, job_id)


@router.patch("/{job_id}", response_model=JobPostResponse)
async def update_my_job(
    job_id: int,
    data: JobPostUpdate,
    current_user: User = Depends(_employer),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_job(db, current_user.id, job_id, data)


@router.patch("/{job_id}/published", response_model=JobPostResponse)
async def set_published(
    job_id: int,
    is_published: bool,
    current_user: User = Depends(_employer),
    db: AsyncSession = Depends(get_db),
):
    """Put a posting on the board, or take it back off."""
    return await service.set_published(db, current_user.id, job_id, is_published)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_job(
    job_id: int,
    current_user: User = Depends(_employer),
    db: AsyncSession = Depends(get_db),
):
    """Deletes the posting and every application on it."""
    await service.delete_job(db, current_user.id, job_id)


@router.post(
    "/{job_id}/promotions",
    response_model=JobPromotionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def promote_my_job(
    job_id: int,
    data: JobPromotionCreate,
    current_user: User = Depends(_employer),
    db: AsyncSession = Depends(get_db),
):
    """Record a paid promotion. `payment_reference` is unique, so the same
    payment cannot buy two."""
    return await service.promote_job(db, current_user.id, job_id, data)


@router.get("/{job_id}/promotions", response_model=List[JobPromotionResponse])
async def list_my_job_promotions(
    job_id: int,
    current_user: User = Depends(_employer),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_promotions(db, current_user.id, job_id)
