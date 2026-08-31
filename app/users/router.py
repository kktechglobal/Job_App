"""What a person can do to their own account.

Signing in lives in app/auth/. Acting on *other people's* accounts lives in
app/admin/. This module is only ever about the caller's own record.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database.db import get_session as get_db
from app.users import service
from app.users.models import User
from app.users.schemas import (
    AccountSettingResponse,
    AccountSettingUpdate,
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_user(db, current_user, data)


@router.get("/me/settings", response_model=AccountSettingResponse)
async def get_my_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Notification and privacy preferences. Defaults are created on first read."""
    return await service.get_settings(db, current_user)


@router.patch("/me/settings", response_model=AccountSettingResponse)
async def update_my_settings(
    data: AccountSettingUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_settings(db, current_user, data)
