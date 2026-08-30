# Append to services/services.py

from app.models.models import CandidateFundingProfile, CandidateProfile, FundingStatus
from app.schemas.schemas import FundingProfileCreate, FundingProfileUpdate

class FundingProfileService:

    @staticmethod
    async def create_funding_profile(
        db: AsyncSession, 
        user_id: int, 
        funding_in: FundingProfileCreate
    ) -> CandidateFundingProfile:
        # Get candidate profile ID
        candidate_res = await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user_id))
        candidate = candidate_res.scalars().first()
        if not candidate:
            raise EntityNotFoundException("Candidate profile not found. Please create a candidate profile first.")

        # Check for existing funding profile
        existing = await db.execute(
            select(CandidateFundingProfile).where(CandidateFundingProfile.candidate_id == candidate.id)
        )
        if existing.scalars().first():
            raise DuplicateResourceException("Funding profile already exists for this candidate.")

        funding_profile = CandidateFundingProfile(
            candidate_id=candidate.id,
            **funding_in.model_dump()
        )
        db.add(funding_profile)
        await db.commit()
        await db.refresh(funding_profile)
        return funding_profile

    @staticmethod
    async def get_by_user_id(db: AsyncSession, user_id: int) -> CandidateFundingProfile:
        candidate_res = await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user_id))
        candidate = candidate_res.scalars().first()
        if not candidate:
            raise EntityNotFoundException("Candidate profile not found")

        result = await db.execute(
            select(CandidateFundingProfile).where(CandidateFundingProfile.candidate_id == candidate.id)
        )
        profile = result.scalars().first()
        if not profile:
            raise EntityNotFoundException("Candidate funding profile not found")
        return profile

    @staticmethod
    async def get_by_id(db: AsyncSession, funding_id: int) -> CandidateFundingProfile:
        result = await db.execute(
            select(CandidateFundingProfile).where(CandidateFundingProfile.id == funding_id)
        )
        profile = result.scalars().first()
        if not profile:
            raise EntityNotFoundException("Funding profile not found")
        return profile

    @staticmethod
    async def list_funding_profiles(
        db: AsyncSession, 
        status_filter: Optional[FundingStatus] = None,
        skip: int = 0, 
        limit: int = 20
    ) -> List[CandidateFundingProfile]:
        query = select(CandidateFundingProfile)
        if status_filter:
            query = query.where(CandidateFundingProfile.status == status_filter)
        
        result = await db.execute(query.offset(skip).limit(limit))
        return result.scalars().all()

    @staticmethod
    async def update_funding_profile(
        db: AsyncSession, 
        user_id: int, 
        funding_in: FundingProfileUpdate
    ) -> CandidateFundingProfile:
        profile = await FundingProfileService.get_by_user_id(db, user_id)

        update_data = funding_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(profile, key, value)

        # Auto-update status based on raised amount
        if profile.amount_raised >= profile.target_amount:
            profile.status = FundingStatus.FULLY_FUNDED
        elif profile.amount_raised > 0 and profile.amount_raised < profile.target_amount:
            profile.status = FundingStatus.PARTIALLY_FUNDED

        await db.commit()
        await db.refresh(profile)
        return profile

    @staticmethod
    async def delete_funding_profile(db: AsyncSession, user_id: int) -> None:
        profile = await FundingProfileService.get_by_user_id(db, user_id)
        await db.delete(profile)
        await db.commit()