from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.models import User, UserRole
from app.schemas.schemas import (
    SavedCandidateCardCreate,
    SavedCandidateCardResponse,
    SavedCandidateCardUpdate
)
from app.services.services import SavedCandidateCardService

router = APIRouter(prefix="/candidate-payment-cards", tags=["Candidate Payment Cards"])

# CREATE: Save a candidate payment card token
@router.post("/", response_model=SavedCandidateCardResponse, status_code=status.HTTP_201_CREATED)
async def save_payment_card(
    card_in: SavedCandidateCardCreate,
    current_user: User = Depends(require_role(UserRole.JOB_SEEKER)),
    db: AsyncSession = Depends(get_db)
):
    return await SavedCandidateCardService.save_card(db, current_user.id, card_in)

# READ ALL: List all saved payment cards for logged-in candidate
@router.get("/", response_model=List[SavedCandidateCardResponse])
async def list_my_payment_cards(
    current_user: User = Depends(require_role(UserRole.JOB_SEEKER)),
    db: AsyncSession = Depends(get_db)
):
    return await SavedCandidateCardService.get_saved_cards(db, current_user.id)

# READ SINGLE: Get specific card details
@router.get("/{card_id}", response_model=SavedCandidateCardResponse)
async def get_payment_card_by_id(
    card_id: int,
    current_user: User = Depends(require_role(UserRole.JOB_SEEKER)),
    db: AsyncSession = Depends(get_db)
):
    return await SavedCandidateCardService.get_card_by_id(db, current_user.id, card_id)

# UPDATE: Update card details or toggle default payment card
@router.patch("/{card_id}", response_model=SavedCandidateCardResponse)
async def update_payment_card(
    card_id: int,
    card_in: SavedCandidateCardUpdate,
    current_user: User = Depends(require_role(UserRole.JOB_SEEKER)),
    db: AsyncSession = Depends(get_db)
):
    return await SavedCandidateCardService.update_card(db, current_user.id, card_id, card_in)

# DELETE: Delete saved payment card
@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment_card(
    card_id: int,
    current_user: User = Depends(require_role(UserRole.JOB_SEEKER)),
    db: AsyncSession = Depends(get_db)
):
    await SavedCandidateCardService.delete_card(db, current_user.id, card_id)
    return None