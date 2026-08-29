
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy.future import select
# from sqlalchemy import or_
# from typing import List, Optional
# from app.job_post.shemas import JobPostCreate
# from app.users.models import users, job_post, application, candidate_profile, applicationStatus, users_Role, users_create
# from app.core.security import get_password_hash
# from app.core.exceptions import DuplicateResourceException, EntityNotFoundException, IncompleteProfileException












# class JobService:

#     async def create_job(db: AsyncSession, employer_id: int, job_in: JobPostCreate) -> job_post:
#         job = job_post(**job_in.model_dump(), employer_id=employer_id, is_published=True)
#         db.add(job)
#         await db.commit()
#         await db.refresh(job)
#         return job

    
#     async def search_jobs(
#         db: AsyncSession, 
#         keyword: Optional[str] = None, 
#         location: Optional[str] = None, 
#         min_salary: Optional[float] = None, 
#         is_remote: Optional[bool] = None
#     ) -> List[job_post]:
#         query = select(job_post).where(job_post.is_published == True)
        
#         if keyword:
#             query = query.where(or_(job_post.title.ilike(f"%{keyword}%"), job_post.description.ilike(f"%{keyword}%")))
#         if location:
#             query = query.where(job_post.location.ilike(f"%{location}%"))
#         if min_salary:
#             query = query.where(job_post.salary_min >= min_salary)
#         if is_remote is not None:
#             query = query.where(job_post.is_remote == is_remote)

#         result = await db.execute(query)
#         return result.scalars().all()

