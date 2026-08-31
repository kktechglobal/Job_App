"""Employer operations: the company, its satellites, and saved payment methods."""

from typing import Optional, Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import func, select, update

from app.companies.models import CompanyContact
from app.companies.models import CompanyFoundingInfo
from app.companies.models import CompanySocialLink
from app.exceptions import DuplicateResourceException, EntityNotFoundException
from app.companies.models import EmployerProfile
from app.companies.schemas import (
    CompanyContactUpsert,
    CompanySocialLinkCreate,
    EmployerProfileCreate,
    EmployerProfileUpdate,
    FoundingInfoUpsert,
)
from app.exceptions import (
    DuplicateResourceException,
    EntityNotFoundException,
    InvalidOperationException,
)
from app.companies.models import EmployerCard
from app.companies.schemas import EmployerCardCreate, EmployerCardUpdate


# ------------------------------------------------------- the company


async def create_company(
    db: AsyncSession, user_id: int, profile_in: EmployerProfileCreate
) -> EmployerProfile:
    existing = await db.execute(
        select(EmployerProfile.id).where(EmployerProfile.user_id == user_id)
    )
    if existing.first():
        raise DuplicateResourceException("This account already has a company profile.")

    profile = EmployerProfile(user_id=user_id, **profile_in.model_dump())
    db.add(profile)
    try:
        await db.commit()
    except IntegrityError as exc:
        # user_id is unique -- two concurrent creates race to here.
        await db.rollback()
        raise DuplicateResourceException(
            "This account already has a company profile."
        ) from exc

    await db.refresh(profile)
    return profile


async def get_company_by_user(db: AsyncSession, user_id: int) -> EmployerProfile:
    result = await db.execute(
        select(EmployerProfile).where(EmployerProfile.user_id == user_id)
    )
    profile = result.scalars().first()
    if not profile:
        raise EntityNotFoundException("Company profile not found.")
    return profile


async def get_company_public(db: AsyncSession, employer_id: int) -> EmployerProfile:
    """The composite read. One query, satellites included."""
    result = await db.execute(
        select(EmployerProfile)
        .where(EmployerProfile.id == employer_id)
        .options(selectinload(EmployerProfile.social_links))
    )
    profile = result.scalars().first()
    if not profile:
        raise EntityNotFoundException("Company not found.")
    return profile


async def update_company(
    db: AsyncSession, user_id: int, profile_in: EmployerProfileUpdate
) -> EmployerProfile:
    profile = await get_company_by_user(db, user_id)
    for field, value in profile_in.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return profile


async def delete_company(db: AsyncSession, user_id: int) -> None:
    profile = await get_company_by_user(db, user_id)
    await db.delete(profile)
    await db.commit()

# -------------------------------------------------- founding info (1:1)


async def get_founding_info(db: AsyncSession, user_id: int) -> CompanyFoundingInfo:
    profile = await get_company_by_user(db, user_id)
    if not profile.founding_info:
        raise EntityNotFoundException("Founding information has not been added yet.")
    return profile.founding_info


async def upsert_founding_info(
    db: AsyncSession, user_id: int, data: FoundingInfoUpsert
) -> CompanyFoundingInfo:
    profile = await get_company_by_user(db, user_id)
    values = data.model_dump()
    values["company_website"] = (
        str(values["company_website"]) if values["company_website"] else None
    )

    row = profile.founding_info
    if row is None:
        row = CompanyFoundingInfo(employer_id=profile.id, **values)
        db.add(row)
    else:
        for field, value in values.items():
            setattr(row, field, value)

    await db.commit()
    await db.refresh(row)
    return row

# -------------------------------------------------------- contact (1:1)


async def get_contact(db: AsyncSession, user_id: int) -> CompanyContact:
    profile = await get_company_by_user(db, user_id)
    if not profile.contact:
        raise EntityNotFoundException("Contact details have not been added yet.")
    return profile.contact


async def upsert_contact(
    db: AsyncSession, user_id: int, data: CompanyContactUpsert
) -> CompanyContact:
    profile = await get_company_by_user(db, user_id)
    values = data.model_dump()

    row = profile.contact
    if row is None:
        row = CompanyContact(employer_id=profile.id, **values)
        db.add(row)
    else:
        for field, value in values.items():
            setattr(row, field, value)

    await db.commit()
    await db.refresh(row)
    return row

# ------------------------------------------------- social links (0..n)


async def list_social_links(
    db: AsyncSession, user_id: int
) -> Sequence[CompanySocialLink]:
    profile = await get_company_by_user(db, user_id)
    result = await db.execute(
        select(CompanySocialLink)
        .where(CompanySocialLink.employer_id == profile.id)
        .order_by(CompanySocialLink.id)
    )
    return result.scalars().all()


async def add_social_link(
    db: AsyncSession, user_id: int, link_in: CompanySocialLinkCreate
) -> CompanySocialLink:
    profile = await get_company_by_user(db, user_id)

    link = CompanySocialLink(
        employer_id=profile.id, platform=link_in.platform, url=str(link_in.url)
    )
    db.add(link)
    try:
        await db.commit()
    except IntegrityError as exc:
        # uq_company_social_platform: one row per platform per company.
        await db.rollback()
        raise DuplicateResourceException(
            f"A {link_in.platform.value} link already exists."
        ) from exc

    await db.refresh(link)
    return link


async def delete_social_link(db: AsyncSession, user_id: int, link_id: int) -> None:
    profile = await get_company_by_user(db, user_id)
    result = await db.execute(
        select(CompanySocialLink).where(
            CompanySocialLink.id == link_id,
            CompanySocialLink.employer_id == profile.id,
        )
    )
    link = result.scalars().first()
    if not link:
        raise EntityNotFoundException("Social link not found.")

    await db.delete(link)
    await db.commit()


async def _employer_for_user(db: AsyncSession, user_id: int) -> EmployerProfile:
    result = await db.execute(
        select(EmployerProfile).where(EmployerProfile.user_id == user_id)
    )
    profile = result.scalars().first()
    if not profile:
        raise EntityNotFoundException(
            "Employer profile not found. Please create a profile first."
        )
    return profile


async def _clear_default_card(
    db: AsyncSession, employer_id: int, *, keep: Optional[int] = None
) -> None:
    """Drop the current default, then flush so the index is free."""
    stmt = (
        update(EmployerCard)
        .where(
            EmployerCard.employer_id == employer_id,
            EmployerCard.is_default.is_(True),
        )
        .values(is_default=False)
    )
    if keep is not None:
        stmt = stmt.where(EmployerCard.id != keep)
    await db.execute(stmt)
    await db.flush()


async def create_card(
    db: AsyncSession, user_id: int, card_in: EmployerCardCreate
) -> EmployerCard:
    employer = await _employer_for_user(db, user_id)

    duplicate = await db.execute(
        select(EmployerCard.id).where(
            EmployerCard.employer_id == employer.id,
            EmployerCard.provider == card_in.provider,
            EmployerCard.payment_method_ref == card_in.payment_method_ref,
        )
    )
    if duplicate.first():
        raise DuplicateResourceException("This card is already saved.")

    saved_already = await db.execute(
        select(func.count())
        .select_from(EmployerCard)
        .where(EmployerCard.employer_id == employer.id)
    )
    # A first card is always the default; otherwise nobody has one.
    make_default = card_in.is_default or saved_already.scalar_one() == 0

    if make_default:
        await _clear_default_card(db, employer.id)

    card = EmployerCard(
        employer_id=employer.id,
        **card_in.model_dump(exclude={"is_default"}),
        is_default=make_default,
    )
    db.add(card)
    try:
        await db.commit()
    except IntegrityError as exc:
        # (provider, payment_method_ref) is unique across the whole table,
        # so the same token saved by someone else lands here too.
        await db.rollback()
        raise DuplicateResourceException("This card cannot be saved.") from exc

    await db.refresh(card)
    return card


async def list_cards(db: AsyncSession, user_id: int) -> Sequence[EmployerCard]:
    employer = await _employer_for_user(db, user_id)
    result = await db.execute(
        select(EmployerCard)
        .where(EmployerCard.employer_id == employer.id)
        .order_by(EmployerCard.is_default.desc(), EmployerCard.created_at, EmployerCard.id)
    )
    return result.scalars().all()


async def get_card(db: AsyncSession, user_id: int, card_id: int) -> EmployerCard:
    employer = await _employer_for_user(db, user_id)
    result = await db.execute(
        select(EmployerCard).where(
            EmployerCard.id == card_id,
            EmployerCard.employer_id == employer.id,
        )
    )
    card = result.scalars().first()
    if not card:
        raise EntityNotFoundException("Payment card not found.")
    return card


async def update_card(
    db: AsyncSession, user_id: int, card_id: int, card_in: EmployerCardUpdate
) -> EmployerCard:
    card = await get_card(db, user_id, card_id)
    data = card_in.model_dump(exclude_unset=True)

    # Expiry arrives one field at a time, so check the pair that will
    # actually be stored, not just what was sent.
    if "exp_month" in data or "exp_year" in data:
        month = data.get("exp_month", card.exp_month)
        year = data.get("exp_year", card.exp_year)
        today = date.today()
        if (year, month) < (today.year, today.month):
            raise InvalidOperationException("That expiry date is in the past.")

    wants_default = data.pop("is_default", None)
    if wants_default is False and card.is_default:
        raise InvalidOperationException(
            "Set another card as default instead of unsetting this one."
        )
    if wants_default is True and not card.is_default:
        await _clear_default_card(db, card.employer_id, keep=card.id)
        card.is_default = True

    for field, value in data.items():
        setattr(card, field, value)

    await db.commit()
    await db.refresh(card)
    return card


async def delete_card(db: AsyncSession, user_id: int, card_id: int) -> None:
    card = await get_card(db, user_id, card_id)
    was_default, employer_id = card.is_default, card.employer_id

    await db.delete(card)
    await db.flush()

    # Deleting the default would otherwise leave the account with none.
    if was_default:
        successor = await db.execute(
            select(EmployerCard)
            .where(EmployerCard.employer_id == employer_id)
            .order_by(EmployerCard.created_at, EmployerCard.id)
            .limit(1)
        )
        promoted = successor.scalars().first()
        if promoted:
            promoted.is_default = True

    await db.commit()
