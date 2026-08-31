"""Request/response shapes for administrator operations.

Nothing here lets an administrator write a password, a role, or a company's
own content. Admin power is deliberately narrow: enable or disable an account,
approve or un-approve a job post, and read. Anything wider belongs in a
deliberate, separately-reviewed endpoint rather than a general admin body.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.admin.enums import AdminAction, AdminTarget
from app.users.enums import UserRole


class SetUserActive(BaseModel):
    is_active: bool
    note: Optional[str] = Field(
        default=None, max_length=500,
        description="Why. Recorded on the audit trail.",
    )


class SetJobApproval(BaseModel):
    is_approved: bool
    note: Optional[str] = Field(default=None, max_length=500)


class AdminUserResponse(BaseModel):
    """Wider than the public UserResponse -- an administrator reviewing an
    account needs to see whether it is locked out. Still no password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    is_email_verified: bool
    created_at: datetime


class AdminJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employer_id: int
    title: str
    job_role: str
    is_published: bool
    is_approved_by_admin: bool
    created_at: datetime
    expiration_date: datetime


class AdminActionLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    admin_id: int
    action: AdminAction
    target_type: AdminTarget
    target_id: int
    note: Optional[str]
    created_at: datetime


class Page(BaseModel):
    """Paged results. An admin list over every user in the system must not
    return the whole table because someone opened a screen."""

    total: int
    limit: int
    offset: int


class UserPage(Page):
    items: List[AdminUserResponse]


class JobPage(Page):
    items: List[AdminJobResponse]


class AuditLogPage(Page):
    items: List[AdminActionLogResponse]
