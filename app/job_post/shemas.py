# from pydantic import BaseModel, EmailStr, Field
# from datetime import datetime
# from typing import Optional, List
# from app.users.schemas import UserRole, ApplicationStatus, JobType





# class JobPostCreate(BaseModel):
#     title: str
#     description: str
#     location: str
#     salary_min: float
#     salary_max: float
#     is_remote: bool
#     job_type: JobType
#     required_skills: List[str]

# class JobPostResponse(JobPostCreate):
#     id: int
#     employer_id: int
#     is_published: bool
#     is_approved_by_admin: bool
#     created_at: datetime

#     class Config:
#         from_attributes = True
