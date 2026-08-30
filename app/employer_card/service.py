# Append to services/services.py

from app.models.models import SavedEmployerCard, EmployerProfile
from app.schemas.schemas import SavedEmployerCardCreate, SavedEmployerCardUpdate

class SavedEmployerCardService:

    @staticmethod
    async def get_employer_profile(db: AsyncSession, user_id: int) -> EmployerProfile:
        result = await db.execute(select(EmployerProfile).where(EmployerProfile.user_id == user_id))
        employer = result.scalars().first()
        if not employer:
            raise EntityNotFoundException("Employer profile not found.")
        return employer

    # CREATE: Save a new payment card
    @staticmethod
    async def save_card(
        db: AsyncSession, 
        user_id: int, 
        card_in: SavedEmployerCardCreate
    ) -> SavedEmployerCard:
        employer = await SavedEmployerCardService.get_employer_profile(db, user_id)

        # Check if card with this token already exists
        token_check = await db.execute(
            select(SavedEmployerCard).where(SavedEmployerCard.payment_token == card_in.payment_token)
        )
        if token_check.scalars().first():
            raise DuplicateResourceException("This card has already been saved.")

        # If this card is set as default, unset other defaults
        if card_in.is_default:
            await db.execute(
                select(SavedEmployerCard)
                .where(SavedEmployerCard.employer_id == employer.id, SavedEmployerCard.is_default == True)
            )
            existing_cards = (await db.execute(
                select(SavedEmployerCard).where(SavedEmployerCard.employer_id == employer.id)
            )).scalars().all()
            for card in existing_cards:
                card.is_default = False

        new_card = SavedEmployerCard(
            employer_id=employer.id,
            **card_in.model_dump()
        )
        db.add(new_card)
        await db.commit()
        await db.refresh(new_card)
        return new_card

    # READ ALL: Get all saved cards for the authenticated employer
    @staticmethod
    async def get_saved_cards(db: AsyncSession, user_id: int) -> List[SavedEmployerCard]:
        employer = await SavedEmployerCardService.get_employer_profile(db, user_id)
        result = await db.execute(
            select(SavedEmployerCard).where(SavedEmployerCard.employer_id == employer.id)
        )
        return result.scalars().all()

    # READ SINGLE: Fetch card details by card ID
    @staticmethod
    async def get_card_by_id(db: AsyncSession, user_id: int, card_id: int) -> SavedEmployerCard:
        employer = await SavedEmployerCardService.get_employer_profile(db, user_id)
        result = await db.execute(
            select(SavedEmployerCard).where(
                SavedEmployerCard.id == card_id, 
                SavedEmployerCard.employer_id == employer.id
            )
        )
        card = result.scalars().first()
        if not card:
            raise EntityNotFoundException("Payment card not found.")
        return card

    # UPDATE: Set card as default or update expiration details
    @staticmethod
    async def update_card(
        db: AsyncSession, 
        user_id: int, 
        card_id: int, 
        card_in: SavedEmployerCardUpdate
    ) -> SavedEmployerCard:
        card = await SavedEmployerCardService.get_card_by_id(db, user_id, card_id)
        update_data = card_in.model_dump(exclude_unset=True)

        if update_data.get("is_default") is True:
            # Unset default flag for all other cards belonging to this employer
            all_cards = (await db.execute(
                select(SavedEmployerCard).where(SavedEmployerCard.employer_id == card.employer_id)
            )).scalars().all()
            for c in all_cards:
                c.is_default = False

        for key, value in update_data.items():
            setattr(card, key, value)

        await db.commit()
        await db.refresh(card)
        return card

    # DELETE: Delete a saved payment card
    @staticmethod
    async def delete_card(db: AsyncSession, user_id: int, card_id: int) -> None:
        card = await SavedEmployerCardService.get_card_by_id(db, user_id, card_id)
        await db.delete(card)
        await db.commit()