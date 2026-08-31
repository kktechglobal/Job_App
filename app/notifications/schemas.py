"""Shapes for outbound messages."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.notifications.enums import NotificationChannel, NotificationStatus


class NotificationCreate(BaseModel):
    user_id: int
    channel: NotificationChannel = NotificationChannel.EMAIL
    subject: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1)


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    channel: NotificationChannel
    subject: str
    body: str
    status: NotificationStatus
    attempts: int
    created_at: datetime
    sent_at: Optional[datetime]
