"""The job seeker's profile.

Everything a candidate says about themselves: headline, bio, skills and social
links. Saved payment methods live in app/candidates/cards/ -- same person,
but a different surface with different handling rules.
"""

from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates import service
from app.candidates.schemas import (
    CandidateProfileCreate,
    CandidateProfileResponse,
    CandidateProfileUpdate,
    SocialLinkCreate,
    SocialLinkResponse,
)
from app.auth.dependencies import require_role
from app.database.db import get_session as get_db
from app.users.models import User, UserRole



router = APIRouter(prefix="/candidate-profile", tags=["Candidate Profile"])


@router.post("", response_model=CandidateProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_my_profile(
    profile_in: CandidateProfileCreate,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncSession = Depends(get_db),
):
    """Create the caller's profile. One per user; a second attempt is a 409."""
    return await service.create_profile(db, current_user.id, profile_in)


@router.get("/me", response_model=CandidateProfileResponse)
async def get_my_profile(
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_profile_by_user(db, current_user.id)


@router.patch("/me", response_model=CandidateProfileResponse)
async def update_my_profile(
    profile_in: CandidateProfileUpdate,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncSession = Depends(get_db),
):
    """Only the fields you send change. Sending `skills` replaces the whole set."""
    return await service.update_profile(db, current_user.id, profile_in)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_profile(
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_profile(db, current_user.id)


@router.get("/me/skills", response_model=List[str])
async def get_my_skills(
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncSession = Depends(get_db),
):
    profile = await service.get_profile_by_user(db, current_user.id)
    return [skill.name for skill in profile.skills]


@router.get("/me/social-links", response_model=List[SocialLinkResponse])
async def get_my_social_links(
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_social_links(db, current_user.id)


@router.post(
    "/me/social-links",
    response_model=SocialLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_my_social_link(
    link_in: SocialLinkCreate,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncSession = Depends(get_db),
):
    """One link per platform. A second link for the same platform is a 409."""
    return await service.add_social_link(db, current_user.id, link_in)


@router.delete("/me/social-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_social_link(
    link_id: int,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_social_link(db, current_user.id, link_id)


@router.get("/{profile_id}", response_model=CandidateProfileResponse)
async def get_profile_by_id(
    profile_id: int,
    current_user: User = Depends(require_role(UserRole.EMPLOYER)),
    db: AsyncSession = Depends(get_db),
):
    """Employers viewing a candidate. Contact details are part of the response,
    so this is deliberately not public."""
    return await service.get_profile_by_id(db, profile_id)
