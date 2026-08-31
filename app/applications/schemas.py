"""Request/response shapes for job applications."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.applications.enums import ApplicationStatus


class ApplicationCreate(BaseModel):
    job_id: int
    cover_letter: Optional[str] = None


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    candidate_id: int
    status: ApplicationStatus
    cover_letter: Optional[str]
    # Computed at apply time from the skills both sides held then. Kept on the
    # row so a later edit to either profile does not silently rewrite history.
    match_score: float = Field(..., ge=0, le=100)
    submitted_at: datetime
    updated_at: datetime
