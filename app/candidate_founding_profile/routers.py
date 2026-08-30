from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.models import User, UserRole, FundingStatus
from app.schemas.schemas import (
    FundingProfileCreate, 
    FundingProfileResponse, 
    FundingProfileUpdate
)
from app.services.services import FundingProfileService

router = APIRouter(prefix="/candidate-funding", tags=["Candidate Funding Profile"])

# CREATE: Candidate creates their funding request profile
@router.post("/", response_model=FundingProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_funding_profile(
    funding_in: FundingProfileCreate,
    current_user: User = Depends(require_role(UserRole.JOB_SEEKER)),
    db: AsyncSession = Depends(get_db)
):
    return await FundingProfileService.create_funding_profile(db, current_user.id, funding_in)

# READ (CURRENT USER): Fetch logged-in candidate's funding profile
@router.get("/me", response_model=FundingProfileResponse)
async def get_my_funding_profile(
    current_user: User = Depends(require_role(UserRole.JOB_SEEKER)),
    db: AsyncSession = Depends(get_db)
):
    return await FundingProfileService.get_by_user_id(db, current_user.id)

# READ ALL: Public/Employers/Sponsors list candidate funding profiles
@router.get("/", response_model=List[FundingProfileResponse])
async def list_funding_profiles(
    status_filter: Optional[FundingStatus] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    return await FundingProfileService.list_funding_profiles(db, status_filter, skip, limit)

# READ BY ID: Public details of a specific funding profile
@router.get("/{funding_id}", response_model=FundingProfileResponse)
async def get_funding_profile_by_id(
    funding_id: int,
    db: AsyncSession = Depends(get_db)
):
    return await FundingProfileService.get_by_id(db, funding_id)

# UPDATE: Candidate updates target, description, or status
@router.patch("/me", response_model=FundingProfileResponse)
async def update_my_funding_profile(
    funding_in: FundingProfileUpdate,
    current_user: User = Depends(require_role(UserRole.JOB_SEEKER)),
    db: AsyncSession = Depends(get_db)
):
    return await FundingProfileService.update_funding_profile(db, current_user.id, funding_in)

# DELETE: Candidate removes funding profile
@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_funding_profile(
    current_user: User = Depends(require_role(UserRole.JOB_SEEKER)),
    db: AsyncSession = Depends(get_db)
):
    await FundingProfileService.delete_funding_profile(db, current_user.id)
    return None