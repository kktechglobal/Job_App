from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_
from typing import List, Optional
from app.job_post.shemas import job_postcreate
from app.users.models import users, job_post, application, candidate_profile, applicationStatus, users_Role, users_create
from app.core.security import get_password_hash
from app.core.exceptions import DuplicateResourceException, EntityNotFoundException, IncompleteProfileException






class ApplicationService:
    
    def _calculate_match_score(candidate_skills: List[str], required_skills: List[str]) -> float:
        if not required_skills:
            return 100.0
        matches = set(candidate_skills).intersection(set(required_skills))
        return round((len(matches) / len(required_skills)) * 100, 2)

    
    async def quick_apply(db: AsyncSession, candidate_user_id: int, job_id: int, cover_letter: Optional[str]) -> application:
        profile_res = await db.execute(select(candidate_profile).where(candidate_profile.user_id == candidate_user_id))
        profile = profile_res.scalars().first()
        
        if not profile or profile.completeness_score < 80:
            raise IncompleteProfileException()

        job_res = await db.execute(select(job_post).where(job_post.id == job_id))
        job = job_res.scalars().first()
        if not job:
            raise EntityNotFoundException("Job posting not found")

        score = ApplicationService._calculate_match_score(profile.skills, job.required_skills)

        application = application(
            job_id=job_id,
            candidate_id=profile.id,
            cover_letter=cover_letter,
            match_score=score,
            status=applicationStatus.SUBMITTED
        )
        db.add(application)
        await db.commit()
        await db.refresh(application)
        return application