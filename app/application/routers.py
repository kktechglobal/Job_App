from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.schemas.schemas import ApplicationCreate, ApplicationResponse, ApplicationStatusUpdate
from app.services.services import ApplicationService
from app.models.models import User, UserRole, Application, CandidateProfile, ApplicationStatus
from app.core.exceptions import EntityNotFoundException

router = APIRouter(prefix="/applications", tags=["Applications"])

@router.post("/quick-apply", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def quick_apply(
    app_in: ApplicationCreate,
    current_user: User = Depends(require_role(UserRole.JOB_SEEKER)),
    db: AsyncSession = Depends(get_db)
):
    return await ApplicationService.quick_apply(db, current_user.id, app_in.job_id, app_in.cover_letter)

@router.get("/my-applications", response_model=List[ApplicationResponse])
async def get_candidate_applications(
    current_user: User = Depends(require_role(UserRole.JOB_SEEKER)),
    db: AsyncSession = Depends(get_db)
):
    profile_res = await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == current_user.id))
    profile = profile_res.scalars().first()
    
    result = await db.execute(select(Application).where(Application.candidate_id == profile.id))
    return result.scalars().all()

@router.patch("/{application_id}/status", response_model=ApplicationResponse)
async def update_application_status(
    application_id: int,
    status_update: ApplicationStatusUpdate,
    current_user: User = Depends(require_role(UserRole.EMPLOYER)),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Application).where(Application.id == application_id))
    app = res.scalars().first()
    if not app:
        raise EntityNotFoundException("Application not found")
    
    app.status = status_update.status
    await db.commit()
    await db.refresh(app)
    return app