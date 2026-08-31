"""A candidate's saved payment methods.

Kept apart from the profile because the handling rules are different: the
provider refs these routes accept are write-only, and nothing here may ever
return them. See app/candidates/models.py for what must never become a column.
"""

from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.candidates import service
from app.database.db import get_session as get_db
from app.users.models import User, UserRole
from app.candidates.schemas import (
    CandidateCardCreate,
    CandidateCardResponse,
    CandidateCardUpdate,
)



router = APIRouter(
    prefix="/candidate-payment-cards", tags=["Candidate Payment Cards"],
    dependencies=[Depends(require_role(UserRole.CANDIDATE))],
)


def _card_owner(current_user: User = Depends(require_role(UserRole.CANDIDATE))) -> User:
    """The router-level dependency enforces the gate; this one hands the
    handler the caller's identity so it can scope the query."""
    return current_user


@router.post("", response_model=CandidateCardResponse, status_code=status.HTTP_201_CREATED)
async def save_payment_card(
    card_in: CandidateCardCreate,
    current_user: User = Depends(_card_owner),
    db: AsyncSession = Depends(get_db),
):
    """Store the refs a payment provider returned for a tokenised card."""
    return await service.create_card(db, current_user.id, card_in)


@router.get("", response_model=List[CandidateCardResponse])
async def list_my_payment_cards(
    current_user: User = Depends(_card_owner),
    db: AsyncSession = Depends(get_db),
):
    """Saved cards, default first."""
    return await service.list_cards(db, current_user.id)


@router.get("/{card_id}", response_model=CandidateCardResponse)
async def get_payment_card(
    card_id: int,
    current_user: User = Depends(_card_owner),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_card(db, current_user.id, card_id)


@router.patch("/{card_id}", response_model=CandidateCardResponse)
async def update_payment_card(
    card_id: int,
    card_in: CandidateCardUpdate,
    current_user: User = Depends(_card_owner),
    db: AsyncSession = Depends(get_db),
):
    """Rename the holder, correct the expiry, or make this card the default."""
    return await service.update_card(db, current_user.id, card_id, card_in)


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment_card(
    card_id: int,
    current_user: User = Depends(_card_owner),
    db: AsyncSession = Depends(get_db),
):
    """Remove a card. If it was the default, the oldest remaining card takes over."""
    await service.delete_card(db, current_user.id, card_id)
