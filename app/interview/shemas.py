# from pydantic import BaseModel, EmailStr, Field
# from datetime import datetime
# from typing import Optional, List
# from app.users.schemas import UserRole, ApplicationStatus, JobType

# # Interview Schemas
# class InterviewSchedule(BaseModel):
#     application_id: int
#     scheduled_time: datetime
#     meeting_link: str
#     notes: Optional[str] = None

# class InterviewResponse(InterviewSchedule):
#     id: int

#     class Config:
#         from_attributes = True