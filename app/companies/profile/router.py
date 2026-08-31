"""The employer's company.

Four resources, not one flat body: the core profile, two 1:1 satellites
written with PUT, and a link collection. Reads go the other way -- one
composite GET returns the whole company so a client renders a page in a single
call. Saved payment methods live in app/companies/cards/.
"""

from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.companies import service
from app.auth.dependencies import get_current_user, require_role
from app.database.db import get_session as get_db
from app.companies.schemas import (
    CompanyContactResponse,
    CompanyContactUpsert,
    CompanySocialLinkCreate,
    CompanySocialLinkResponse,
    EmployerProfileCreate,
    EmployerProfileResponse,
    EmployerProfileUpdate,
    FoundingInfoResponse,
    FoundingInfoUpsert,
    PublicCompanyResponse,
)
from app.users.models import User, UserRole
from app.auth.dependencies import require_role



router = APIRouter(prefix="/employer-profile", tags=["Employer Profile"])


# ------------------------------------------------------------- the company

@router.post("", response_model=EmployerProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_my_company(
    profile_in: EmployerProfileCreate,
    current_user: User = Depends(require_role(UserRole.EMPLOYER)),
    db: AsyncSession = Depends(get_db),
):
    """Create the caller's company. One per user; a second attempt is a 409."""
    return await service.create_company(db, current_user.id, profile_in)


@router.get("/me", response_model=EmployerProfileResponse)
async def get_my_company(
    current_user: User = Depends(require_role(UserRole.EMPLOYER)),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_company_by_user(db, current_user.id)


@router.patch("/me", response_model=EmployerProfileResponse)
async def update_my_company(
    profile_in: EmployerProfileUpdate,
    current_user: User = Depends(require_role(UserRole.EMPLOYER)),
    db: AsyncSession = Depends(get_db),
):
    """Only the fields you send change. Verification and billing state are
    not writable here."""
    return await service.update_company(db, current_user.id, profile_in)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_company(
    current_user: User = Depends(require_role(UserRole.EMPLOYER)),
    db: AsyncSession = Depends(get_db),
):
    """Removes the company and everything hanging off it: founding info,
    contact, links, saved cards and job posts."""
    await service.delete_company(db, current_user.id)


# ------------------------------------------------------------ founding info

@router.get("/me/founding-info", response_model=FoundingInfoResponse)
async def get_my_founding_info(
    current_user: User = Depends(require_role(UserRole.EMPLOYER)),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_founding_info(db, current_user.id)


@router.put("/me/founding-info", response_model=FoundingInfoResponse)
async def save_my_founding_info(
    data: FoundingInfoUpsert,
    current_user: User = Depends(require_role(UserRole.EMPLOYER)),
    db: AsyncSession = Depends(get_db),
):
    """PUT, not POST: there is exactly one of these per company, so sending it
    twice is not an error and does not create a second row."""
    return await service.upsert_founding_info(db, current_user.id, data)


# ------------------------------------------------------------------ contact

@router.get("/me/contact", response_model=CompanyContactResponse)
async def get_my_contact(
    current_user: User = Depends(require_role(UserRole.EMPLOYER)),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_contact(db, current_user.id)


@router.put("/me/contact", response_model=CompanyContactResponse)
async def save_my_contact(
    data: CompanyContactUpsert,
    current_user: User = Depends(require_role(UserRole.EMPLOYER)),
    db: AsyncSession = Depends(get_db),
):
    """The company's public contact details, not the owner's login email."""
    return await service.upsert_contact(db, current_user.id, data)


# ------------------------------------------------------------- social links

@router.get("/me/social-links", response_model=List[CompanySocialLinkResponse])
async def get_my_social_links(
    current_user: User = Depends(require_role(UserRole.EMPLOYER)),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_social_links(db, current_user.id)


@router.post(
    "/me/social-links",
    response_model=CompanySocialLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_my_social_link(
    link_in: CompanySocialLinkCreate,
    current_user: User = Depends(require_role(UserRole.EMPLOYER)),
    db: AsyncSession = Depends(get_db),
):
    """One link per platform. A second link for the same platform is a 409."""
    return await service.add_social_link(db, current_user.id, link_in)


@router.delete("/me/social-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_social_link(
    link_id: int,
    current_user: User = Depends(require_role(UserRole.EMPLOYER)),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_social_link(db, current_user.id, link_id)


# --------------------------------------------------------- the company page

# Declared last: "/me" above must win over "/{employer_id}".
@router.get("/{employer_id}", response_model=PublicCompanyResponse)
async def get_company(
    employer_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The whole company in one response, for the public company page.

    Any signed-in user may read it -- candidates browse employers. It is not
    anonymous, because the response carries the company's contact details and
    an open endpoint is a scraping target.
    """
    return await service.get_company_public(db, employer_id)
