"""An employer's saved payment methods.

Kept apart from the company profile for the same reason as the candidate side:
the provider refs are write-only, and nothing here may ever return them.
"""

from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.auth.dependencies import require_role
from app.companies import service
from app.database.db import get_session as get_db
from app.users.models import User, UserRole
from app.companies.schemas import (
    EmployerCardCreate,
    EmployerCardResponse,
    EmployerCardUpdate,
)



router = APIRouter(
    prefix="/employer-payment-cards", tags=["Employer Payment Cards"],
    dependencies=[Depends(require_role(UserRole.EMPLOYER))],
)


def _card_owner(current_user: User = Depends(require_role(UserRole.EMPLOYER))) -> User:
    """The router-level dependency enforces the gate; this one hands the
    handler the caller's identity so it can scope the query."""
    return current_user


@router.post("", response_model=EmployerCardResponse, status_code=status.HTTP_201_CREATED)
async def save_payment_card(
    card_in: EmployerCardCreate,
    current_user: User = Depends(_card_owner),
    db: AsyncSession = Depends(get_db),
):
    """Store the refs a payment provider returned for a tokenised card."""
    return await service.create_card(db, current_user.id, card_in)


@router.get("", response_model=List[EmployerCardResponse])
async def list_my_payment_cards(
    current_user: User = Depends(_card_owner),
    db: AsyncSession = Depends(get_db),
):
    """Saved cards, default first."""
    return await service.list_cards(db, current_user.id)


@router.get("/{card_id}", response_model=EmployerCardResponse)
async def get_payment_card(
    card_id: int,
    current_user: User = Depends(_card_owner),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_card(db, current_user.id, card_id)


@router.patch("/{card_id}", response_model=EmployerCardResponse)
async def update_payment_card(
    card_id: int,
    card_in: EmployerCardUpdate,
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
