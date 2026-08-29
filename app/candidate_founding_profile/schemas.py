from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List
from app.users.schemas import UserRole, ApplicationStatus, JobType




class CandidateProfileCreate(BaseModel):
    headline: Optional[str] = None
    resume_url: Optional[str] = None
    skills: List[str] = []
    years_experience: int = 0

class CandidateProfileResponse(CandidateProfileCreate):
    id: int
    completeness_score: int

    class Config:
        from_attributes = True