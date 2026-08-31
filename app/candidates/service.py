"""Job-seeker operations: the profile, its social links, and saved payment methods."""

from typing import List, Optional, Sequence
from datetime import date
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import func, select, update

from app.candidates.models import CandidateProfile
from app.candidates.schemas import (
    CandidateProfileCreate,
    CandidateProfileUpdate,
    SocialLinkCreate,
)
from app.candidates.models import CandidateSocialLink
from app.exceptions import DuplicateResourceException, EntityNotFoundException
from app.skills.models import Skill
from app.candidates.models import CandidateCard
from app.candidates.schemas import CandidateCardCreate, CandidateCardUpdate
from app.exceptions import (
    DuplicateResourceException,
    EntityNotFoundException,
    InvalidOperationException,
)


async def _resolve_skills(db: AsyncSession, names: List[str]) -> List[Skill]:
    """Map skill names onto Skill rows, creating the ones that are new."""
    if not names:
        return []

    found = await db.execute(select(Skill).where(Skill.name.in_(names)))
    existing = {skill.name: skill for skill in found.scalars().all()}

    for name in names:
        if name not in existing:
            skill = Skill(name=name)
            db.add(skill)
            existing[name] = skill

    await db.flush()
    return [existing[name] for name in names]


async def create_profile(
    db: AsyncSession, user_id: int, profile_in: CandidateProfileCreate
) -> CandidateProfile:
    existing = await db.execute(
        select(CandidateProfile.id).where(CandidateProfile.user_id == user_id)
    )
    if existing.first():
        raise DuplicateResourceException("This account already has a candidate profile.")

    data = profile_in.model_dump(exclude={"skills"})
    profile = CandidateProfile(user_id=user_id, **data)
    profile.skills = await _resolve_skills(db, profile_in.skills)

    db.add(profile)
    try:
        await db.commit()
    except IntegrityError as exc:
        # user_id is unique -- two concurrent creates race to here.
        await db.rollback()
        raise DuplicateResourceException(
            "This account already has a candidate profile."
        ) from exc

    await db.refresh(profile)
    return profile


async def get_profile_by_user(db: AsyncSession, user_id: int) -> CandidateProfile:
    result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == user_id)
    )
    profile = result.scalars().first()
    if not profile:
        raise EntityNotFoundException("Candidate profile not found.")
    return profile


async def get_profile_by_id(db: AsyncSession, profile_id: int) -> CandidateProfile:
    result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.id == profile_id)
    )
    profile = result.scalars().first()
    if not profile:
        raise EntityNotFoundException("Candidate profile not found.")
    return profile


async def update_profile(
    db: AsyncSession, user_id: int, profile_in: CandidateProfileUpdate
) -> CandidateProfile:
    profile = await get_profile_by_user(db, user_id)
    data = profile_in.model_dump(exclude_unset=True)

    skills = data.pop("skills", None)
    if skills is not None:
        profile.skills = await _resolve_skills(db, skills)

    for field, value in data.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return profile


async def delete_profile(db: AsyncSession, user_id: int) -> None:
    profile = await get_profile_by_user(db, user_id)
    await db.delete(profile)
    await db.commit()

# ------------------------------------------------ social links


async def list_social_links(db: AsyncSession, user_id: int) -> Sequence[CandidateSocialLink]:
    profile = await get_profile_by_user(db, user_id)
    result = await db.execute(
        select(CandidateSocialLink)
        .where(CandidateSocialLink.candidate_id == profile.id)
        .order_by(CandidateSocialLink.id)
    )
    return result.scalars().all()


async def add_social_link(
    db: AsyncSession, user_id: int, link_in: SocialLinkCreate
) -> CandidateSocialLink:
    profile = await get_profile_by_user(db, user_id)

    link = CandidateSocialLink(
        candidate_id=profile.id,
        platform=link_in.platform,
        url=str(link_in.url),
    )
    db.add(link)
    try:
        await db.commit()
    except IntegrityError as exc:
        # uq_candidate_social_platform: one row per platform per candidate.
        await db.rollback()
        raise DuplicateResourceException(
            f"A {link_in.platform.value} link already exists."
        ) from exc

    await db.refresh(link)
    return link


async def delete_social_link(db: AsyncSession, user_id: int, link_id: int) -> None:
    profile = await get_profile_by_user(db, user_id)
    result = await db.execute(
        select(CandidateSocialLink).where(
            CandidateSocialLink.id == link_id,
            CandidateSocialLink.candidate_id == profile.id,
        )
    )
    link = result.scalars().first()
    if not link:
        raise EntityNotFoundException("Social link not found.")

    await db.delete(link)
    await db.commit()


async def _candidate_for_user(db: AsyncSession, user_id: int) -> CandidateProfile:
    result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == user_id)
    )
    profile = result.scalars().first()
    if not profile:
        raise EntityNotFoundException(
            "Candidate profile not found. Please create a profile first."
        )
    return profile


async def _clear_default_card(
    db: AsyncSession, candidate_id: int, *, keep: Optional[int] = None
) -> None:
    """Drop the current default, then flush so the index is free."""
    stmt = (
        update(CandidateCard)
        .where(
            CandidateCard.candidate_id == candidate_id,
            CandidateCard.is_default.is_(True),
        )
        .values(is_default=False)
    )
    if keep is not None:
        stmt = stmt.where(CandidateCard.id != keep)
    await db.execute(stmt)
    await db.flush()


async def create_card(
    db: AsyncSession, user_id: int, card_in: CandidateCardCreate
) -> CandidateCard:
    candidate = await _candidate_for_user(db, user_id)

    duplicate = await db.execute(
        select(CandidateCard.id).where(
            CandidateCard.candidate_id == candidate.id,
            CandidateCard.provider == card_in.provider,
            CandidateCard.payment_method_ref == card_in.payment_method_ref,
        )
    )
    if duplicate.first():
        raise DuplicateResourceException("This card is already saved.")

    saved_already = await db.execute(
        select(func.count())
        .select_from(CandidateCard)
        .where(CandidateCard.candidate_id == candidate.id)
    )
    # A first card is always the default; otherwise nobody has one.
    make_default = card_in.is_default or saved_already.scalar_one() == 0

    if make_default:
        await _clear_default_card(db, candidate.id)

    card = CandidateCard(
        candidate_id=candidate.id,
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


async def list_cards(db: AsyncSession, user_id: int) -> Sequence[CandidateCard]:
    candidate = await _candidate_for_user(db, user_id)
    result = await db.execute(
        select(CandidateCard)
        .where(CandidateCard.candidate_id == candidate.id)
        .order_by(CandidateCard.is_default.desc(), CandidateCard.created_at, CandidateCard.id)
    )
    return result.scalars().all()


async def get_card(db: AsyncSession, user_id: int, card_id: int) -> CandidateCard:
    candidate = await _candidate_for_user(db, user_id)
    result = await db.execute(
        select(CandidateCard).where(
            CandidateCard.id == card_id,
            CandidateCard.candidate_id == candidate.id,
        )
    )
    card = result.scalars().first()
    if not card:
        raise EntityNotFoundException("Payment card not found.")
    return card


async def update_card(
    db: AsyncSession, user_id: int, card_id: int, card_in: CandidateCardUpdate
) -> CandidateCard:
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
        await _clear_default_card(db, card.candidate_id, keep=card.id)
        card.is_default = True

    for field, value in data.items():
        setattr(card, field, value)

    await db.commit()
    await db.refresh(card)
    return card


async def delete_card(db: AsyncSession, user_id: int, card_id: int) -> None:
    card = await get_card(db, user_id, card_id)
    was_default, candidate_id = card.is_default, card.candidate_id

    await db.delete(card)
    await db.flush()

    # Deleting the default would otherwise leave the account with none.
    if was_default:
        successor = await db.execute(
            select(CandidateCard)
            .where(CandidateCard.candidate_id == candidate_id)
            .order_by(CandidateCard.created_at, CandidateCard.id)
            .limit(1)
        )
        promoted = successor.scalars().first()
        if promoted:
            promoted.is_default = True

    await db.commit()
