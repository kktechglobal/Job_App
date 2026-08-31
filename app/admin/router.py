"""Administrator routes.

These used to live at the bottom of app/users/routers.py, which put moderation
of every account and every job post inside the module that handles sign-up.
They are their own domain now: their own model (the audit trail), schemas,
service and router.

Every route is gated on UserRole.ADMIN. That gate is the only thing standing
between these endpoints and the whole database, so it is applied once at the
router rather than remembered on each handler.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import service
from app.admin.enums import AdminTarget
from app.admin.schemas import (
    AdminJobResponse,
    AdminUserResponse,
    AuditLogPage,
    JobPage,
    SetJobApproval,
    SetUserActive,
    UserPage,
)
from app.auth.dependencies import require_role
from app.database.db import get_session as get_db
from app.users.models import User, UserRole

# One dependency for the whole router: no handler can be added later that
# forgets the role check.
router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)


def _admin(current_user: User = Depends(require_role(UserRole.ADMIN))) -> User:
    """The router-level dependency enforces the gate; this one hands the
    handler the administrator's identity so it can be written to the log."""
    return current_user


# ---------------------------------------------------------------- users

@router.get("/users", response_model=UserPage)
async def list_users(
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = Query(default=None, max_length=200,
                                  description="Matches email or full name"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    items, total = await service.list_users(
        db, role=role, is_active=is_active, search=search, limit=limit, offset=offset
    )
    return UserPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/users/{user_id}", response_model=AdminUserResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    return await service.get_user(db, user_id)


@router.patch("/users/{user_id}/active", response_model=AdminUserResponse)
async def set_user_active(
    user_id: int,
    body: SetUserActive,
    admin: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable an account. Disabling also ends its open sessions.

    You cannot deactivate yourself, and other administrators cannot be changed
    from here.
    """
    return await service.set_user_active(
        db, admin, user_id, body.is_active, body.note
    )


# ----------------------------------------------------------------- jobs

@router.get("/jobs", response_model=JobPage)
async def list_jobs(
    is_approved: Optional[bool] = Query(
        default=None, description="false lists the moderation queue"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    items, total = await service.list_jobs(
        db, is_approved=is_approved, limit=limit, offset=offset
    )
    return JobPage(items=items, total=total, limit=limit, offset=offset)


@router.patch("/jobs/{job_id}/approval", response_model=AdminJobResponse)
async def set_job_approval(
    job_id: int,
    body: SetJobApproval,
    admin: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
):
    """Approve a job post, or withdraw an approval already given."""
    return await service.set_job_approval(
        db, admin, job_id, body.is_approved, body.note
    )


# ------------------------------------------------------------- audit log

@router.get("/audit-log", response_model=AuditLogPage)
async def list_audit_log(
    admin_id: Optional[int] = None,
    target_type: Optional[AdminTarget] = None,
    target_id: Optional[int] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Who did what, newest first. Read-only: there is no endpoint that edits
    or deletes an entry, which is the point of keeping one."""
    items, total = await service.list_audit_log(
        db, admin_id=admin_id, target_type=target_type,
        target_id=target_id, limit=limit, offset=offset,
    )
    return AuditLogPage(items=items, total=total, limit=limit, offset=offset)
