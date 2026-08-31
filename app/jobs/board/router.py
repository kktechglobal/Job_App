"""The public job board.

What anyone signed in can see: postings that are published by their employer,
approved by an administrator, and not yet expired. Drafts and expired listings
belong to app/jobs/management/, which is a different audience with a different
gate.

The board is not anonymous -- an open endpoint over every live vacancy is a
scraping target -- so the router carries `get_current_user` for every route.
"""

from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database.db import get_session as get_db
from app.jobs import service
from app.jobs.enums import ExperienceLevel, JobLevel, JobType
from app.jobs.schemas import JobPostResponse

router = APIRouter(
    prefix="/jobs", tags=["Jobs"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=List[JobPostResponse])
async def search_jobs(
    q: Optional[str] = Query(default=None, max_length=200,
                             description="Matches title, role or description"),
    country: Optional[str] = None,
    city: Optional[str] = None,
    job_type: Optional[JobType] = None,
    job_level: Optional[JobLevel] = None,
    experience_level: Optional[ExperienceLevel] = None,
    fully_remote: Optional[bool] = None,
    salary_min: Optional[Decimal] = Query(default=None, ge=0,
                                          description="Pays at least this much"),
    skill: Optional[str] = Query(default=None, max_length=80),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """The public board: published, admin-approved and not yet expired."""
    items, _ = await service.search_jobs(
        db, q=q, country=country, city=city, job_type=job_type, job_level=job_level,
        experience_level=experience_level, fully_remote=fully_remote,
        salary_min=salary_min, skill=skill, limit=limit, offset=offset,
    )
    return items


@router.get("/{job_id}", response_model=JobPostResponse)
async def get_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await service.get_job_public(db, job_id)


# ------------------------------------------------------ the employer's own
