"""Request/response shapes for interviews.

Times must carry a timezone. The column is DateTime(timezone=True), and a
naive datetime silently means "whatever the server's clock says", which is
the wrong answer for a candidate in another country.
"""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("scheduled_time must include a timezone offset")
    return value


class InterviewCreate(BaseModel):
    application_id: int
    scheduled_time: datetime
    # Required, because the column is NOT NULL.
    meeting_link: str = Field(..., min_length=1, max_length=500)
    notes: Optional[str] = None

    @field_validator("scheduled_time")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return _require_aware(value)

    @model_validator(mode="after")
    def _in_the_future(self) -> "InterviewCreate":
        if self.scheduled_time <= datetime.now(timezone.utc):
            raise ValueError("scheduled_time must be in the future")
        return self


class InterviewUpdate(BaseModel):
    """Only the supplied fields change. `application_id` is absent on purpose:
    moving an interview to a different application is a new booking."""

    scheduled_time: Optional[datetime] = None
    meeting_link: Optional[str] = Field(default=None, min_length=1, max_length=500)
    notes: Optional[str] = None

    @field_validator("scheduled_time")
    @classmethod
    def _aware(cls, value: Optional[datetime]) -> Optional[datetime]:
        return None if value is None else _require_aware(value)


class InterviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    scheduled_time: datetime
    meeting_link: str
    notes: Optional[str]
