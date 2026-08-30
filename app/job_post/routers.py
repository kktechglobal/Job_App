# from fastapi import APIRouter, Depends, Query
# from sqlalchemy.ext.asyncio import AsyncSession
# from typing import List, Optional
# from app.job_post.routers import get_db
# from app.core.dependencies import get_current_user, require_role
# from app.job_post.routers import JobPostCreate, jobpostsResponse
# from app.job_post.routers import JobService
# from app.job_post.routers import User, UserRole, EmployerProfile
# from sqlalchemy.future import select

# router = APIRouter(prefix="/jobs", tags=["Jobs"])



# @router.post("/", response_model=jobpostsResponse)
# async def create_job(
#     job_in: JobPostCreate,
#     current_user: User = Depends(require_role(UserRole.EMPLOYER)),
#     db: AsyncSession = Depends(get_db)
# ):
#     result= await db.execute(select(EmployerProfile).where(EmployerProfile.user_id == current_user.id))
#     result_profile = result.scalars().first()
#     return await JobService.create_job(db, result_profile.id, job_in)



# @router.get("/search", response_model=List[jobpostsResponse])
# async def search_jobs(
#     keyword: Optional[str] = None,
#     location: Optional[str] = None,
#     min_salary: Optional[float] = None,
#     is_remote: Optional[bool] = Query(None),
#     db: AsyncSession = Depends(get_db)
# ):
#     return await JobService.search_jobs(db, keyword, location, min_salary, is_remote)