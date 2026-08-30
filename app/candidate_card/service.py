# Append to services/services.py

from app.models.models import SavedCandidateCard, CandidateProfile
from app.schemas.schemas import SavedCandidateCardCreate, SavedCandidateCardUpdate

class SavedCandidateCardService:

    @staticmethod
    async def get_candidate_profile(db: AsyncSession, user_id: int) -> CandidateProfile:
        result = await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user_id))
        candidate = result.scalars().first()
        if not candidate:
            raise EntityNotFoundException("Candidate profile not found. Please create a profile first.")
        return candidate

    # CREATE: Save a new candidate payment card token
    @staticmethod
    async def save_card(
        db: AsyncSession, 
        user_id: int, 
        card_in: SavedCandidateCardCreate
    ) -> SavedCandidateCard:
        candidate = await SavedCandidateCardService.get_candidate_profile(db, user_id)

        # Check for duplicate token
        token_check = await db.execute(
            select(SavedCandidateCard).where(SavedCandidateCard.payment_token == card_in.payment_token)
        )
        if token_check.scalars().first():
            raise DuplicateResourceException("This card has already been saved.")

        # Handle setting primary default card
        if card_in.is_default:
            existing_cards = (await db.execute(
                select(SavedCandidateCard).where(SavedCandidateCard.candidate_id == candidate.id)
            )).scalars().all()
            for c in existing_cards:
                c.is_default = False

        new_card = SavedCandidateCard(
            candidate_id=candidate.id,
            **card_in.model_dump()
        )
        db.add(new_card)
        await db.commit()
        await db.refresh(new_card)
        return new_card

    # READ ALL: Get all saved cards for the authenticated candidate
    @staticmethod
    async def get_saved_cards(db: AsyncSession, user_id: int) -> List[SavedCandidateCard]:
        candidate = await SavedCandidateCardService.get_candidate_profile(db, user_id)
        result = await db.execute(
            select(SavedCandidateCard).where(SavedCandidateCard.candidate_id == candidate.id)
        )
        return result.scalars().all()

    # READ SINGLE: Get card by ID
    @staticmethod
    async def get_card_by_id(db: AsyncSession, user_id: int, card_id: int) -> SavedCandidateCard:
        candidate = await SavedCandidateCardService.get_candidate_profile(db, user_id)
        result = await db.execute(
            select(SavedCandidateCard).where(
                SavedCandidateCard.id == card_id, 
                SavedCandidateCard.candidate_id == candidate.id
            )
        )
        card = result.scalars().first()
        if not card:
            raise EntityNotFoundException("Payment card not found.")
        return card

    # UPDATE: Modify metadata or switch primary card
    @staticmethod
    async def update_card(
        db: AsyncSession, 
        user_id: int, 
        card_id: int, 
        card_in: SavedCandidateCardUpdate
    ) -> SavedCandidateCard:
        card = await SavedCandidateCardService.get_card_by_id(db, user_id, card_id)
        update_data = card_in.model_dump(exclude_unset=True)

        if update_data.get("is_default") is True:
            all_cards = (await db.execute(
                select(SavedCandidateCard).where(SavedCandidateCard.candidate_id == card.candidate_id)
            )).scalars().all()
            for c in all_cards:
                c.is_default = False

        for key, value in update_data.items():
            setattr(card, key, value)

        await db.commit()
        await db.refresh(card)
        return card

    # DELETE: Remove a saved candidate card
    @staticmethod
    async def delete_card(db: AsyncSession, user_id: int, card_id: int) -> None:
        card = await SavedCandidateCardService.get_card_by_id(db, user_id, card_id)
        await db.delete(card)
        await db.commit()