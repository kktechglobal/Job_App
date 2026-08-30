# from fastapi import APIRouter, Depends, status
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy.future import select
# from app.interview import get_db
# from app.core.dependencies import require_role
# from app.interview.routers import InterviewSchedule, Interview_Response
# from app.interview.routers import UserRole, Interview, JobPost
# from app.core.exceptions import EntityNotFoundException

# interview_router = APIRouter(prefix="/interviews", tags=["Interviews"])

# @interview_router.post("/schedule", response_model=Interview_Response, status_code=status.HTTP_201_CREATED)
# async def schedule_interview(
#     data: InterviewSchedule,
#     current_user=Depends(require_role(UserRole.EMPLOYER)),
#     db: AsyncSession = Depends(get_db)
# ):
#     interview = Interview(**data.model_dump())
#     db.add(interview)
#     await db.commit()
#     await db.refresh(interview)
#     return interview

# @interview_router.get("/job/{job_id}", response_model=list[Interview_Response])
# async def get_interviews_for_job(
#     job_id: int,
#     current_user=Depends(require_role(UserRole.EMPLOYER)),
#     db: AsyncSession = Depends(get_db)
# ):
#     result = await db.execute(select(Interview).where(Interview.job_id == job_id))
#     interviews = result.scalars().all()
#     if not interviews:
#         raise EntityNotFoundException("No interviews found for this job")
#     return interviews

