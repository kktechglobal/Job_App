from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List
from app.users.schemas import UserRole, ApplicationStatus, JobType




class ApplicationCreate(BaseModel):
    job_id: int
    cover_letter: Optional[str] = None

class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus

class ApplicationResponse(BaseModel):
    id: int
    job_id: int
    candidate_id: int
    status: ApplicationStatus
    cover_letter: Optional[str]
    match_score: float
    submitted_at: datetime

    class Config:
        from_attributes = True