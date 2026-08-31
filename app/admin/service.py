"""Administrator operations.

Every state change here does two things in one transaction: the change itself,
and an AdminActionLog row recording who made it. They commit together, so the
audit trail cannot drift out of step with what actually happened.

The account change is applied here rather than delegated to UserService,
because UserService commits on its own. Two commits would mean a window in
which an account is disabled but nothing records who disabled it.
"""

from typing import Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.enums import AdminAction, AdminTarget
from app.admin.models import AdminActionLog
from app.exceptions import EntityNotFoundException, InvalidOperationException
from app.jobs.models import JobPost
from app.users.models import User, UserRole


def _log(
    db: AsyncSession,
    admin: User,
    action: AdminAction,
    target_type: AdminTarget,
    target_id: int,
    note: Optional[str],
) -> AdminActionLog:
    """Staged, not committed. The caller commits it with the change it
    describes so the two cannot come apart."""
    entry = AdminActionLog(
        admin_id=admin.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        note=note,
    )
    db.add(entry)
    return entry

# ---------------------------------------------------------------- users


async def list_users(
    db: AsyncSession,
    *,
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[Sequence[User], int]:
    filters = []
    if role is not None:
        filters.append(User.role == role)
    if is_active is not None:
        filters.append(User.is_active.is_(is_active))
    if search:
        pattern = f"%{search.lower()}%"
        filters.append(
            func.lower(User.email).like(pattern) | func.lower(User.full_name).like(pattern)
        )

    total = await db.execute(select(func.count()).select_from(User).where(*filters))
    rows = await db.execute(
        select(User).where(*filters).order_by(User.id).limit(limit).offset(offset)
    )
    return rows.scalars().all(), total.scalar_one()


async def get_user(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise EntityNotFoundException("User not found.")
    return user


async def set_user_active(
    db: AsyncSession, admin: User, user_id: int, is_active: bool, note: Optional[str]
) -> User:
    target = await get_user(db, user_id)

    # Deactivating yourself ends your own session on the next request, and
    # nothing in this API can undo it. Blocked outright.
    if target.id == admin.id and not is_active:
        raise InvalidOperationException("You cannot deactivate your own account.")

    # One administrator disabling another is an escalation dressed up as
    # moderation. It needs a deliberate process, not this endpoint.
    if target.role == UserRole.ADMIN and target.id != admin.id:
        raise InvalidOperationException(
            "Administrator accounts cannot be changed from here."
        )

    if target.is_active == is_active:
        # Nothing changed, so nothing is logged -- an audit trail full of
        # no-ops is one nobody reads.
        return target

    target.is_active = is_active
    if not is_active:
        # Ends sessions already open, not just future logins.
        target.token_version += 1

    _log(
        db, admin,
        AdminAction.USER_ACTIVATED if is_active else AdminAction.USER_DEACTIVATED,
        AdminTarget.USER, target.id, note,
    )
    await db.commit()
    await db.refresh(target)
    return target

# ----------------------------------------------------------------- jobs


async def list_jobs(
    db: AsyncSession,
    *,
    is_approved: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[Sequence[JobPost], int]:
    filters = []
    if is_approved is not None:
        filters.append(JobPost.is_approved_by_admin.is_(is_approved))

    total = await db.execute(select(func.count()).select_from(JobPost).where(*filters))
    rows = await db.execute(
        select(JobPost).where(*filters)
        .order_by(JobPost.created_at.desc(), JobPost.id.desc())
        .limit(limit).offset(offset)
    )
    return rows.scalars().all(), total.scalar_one()


async def get_job(db: AsyncSession, job_id: int) -> JobPost:
    result = await db.execute(select(JobPost).where(JobPost.id == job_id))
    job = result.scalars().first()
    if not job:
        raise EntityNotFoundException("Job not found.")
    return job


async def set_job_approval(
    db: AsyncSession, admin: User, job_id: int, is_approved: bool, note: Optional[str]
) -> JobPost:
    job = await get_job(db, job_id)

    if job.is_approved_by_admin == is_approved:
        return job

    job.is_approved_by_admin = is_approved
    _log(
        db, admin,
        AdminAction.JOB_APPROVED if is_approved else AdminAction.JOB_APPROVAL_REVOKED,
        AdminTarget.JOB_POST, job.id, note,
    )
    await db.commit()
    await db.refresh(job)
    return job

# ------------------------------------------------------------ audit log


async def list_audit_log(
    db: AsyncSession,
    *,
    admin_id: Optional[int] = None,
    target_type: Optional[AdminTarget] = None,
    target_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[Sequence[AdminActionLog], int]:
    filters = []
    if admin_id is not None:
        filters.append(AdminActionLog.admin_id == admin_id)
    if target_type is not None:
        filters.append(AdminActionLog.target_type == target_type)
    if target_id is not None:
        filters.append(AdminActionLog.target_id == target_id)

    total = await db.execute(
        select(func.count()).select_from(AdminActionLog).where(*filters)
    )
    rows = await db.execute(
        select(AdminActionLog).where(*filters)
        .order_by(AdminActionLog.created_at.desc(), AdminActionLog.id.desc())
        .limit(limit).offset(offset)
    )
    return rows.scalars().all(), total.scalar_one()
