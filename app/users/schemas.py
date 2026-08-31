"""Shapes for an account and its preferences.

Registration and password schemas live in app/auth/ -- this domain describes
what an account *is*, not how someone proves they own it.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.users.enums import UserRole


class UserUpdate(BaseModel):
    """Email is absent on purpose: changing it has to re-run verification,
    which is a separate flow, not a field on this one."""

    full_name: Optional[str] = Field(default=None, min_length=1, max_length=200)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    username: str
    full_name: str
    role: UserRole
    is_active: bool
    is_email_verified: bool
    created_at: datetime


class AccountSettingUpdate(BaseModel):
    email_notifications: Optional[bool] = None
    job_alert_emails: Optional[bool] = None
    profile_is_public: Optional[bool] = None


class AccountSettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    email_notifications: bool
    job_alert_emails: bool
    profile_is_public: bool
