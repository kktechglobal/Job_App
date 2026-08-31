"""Account operations that are not authentication."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import EntityNotFoundException
from app.users.models import AccountSetting, User
from app.users.schemas import AccountSettingUpdate, UserUpdate


async def get_by_id(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise EntityNotFoundException("User not found.")
    return user


async def update_user(db: AsyncSession, user: User, data: UserUpdate) -> User:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


async def get_settings(db: AsyncSession, user: User) -> AccountSetting:
    """Created on first read rather than at registration, so an account
    that never opens the settings screen carries no extra row."""
    if user.settings:
        return user.settings

    row = AccountSetting(user_id=user.id)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_settings(
    db: AsyncSession, user: User, data: AccountSettingUpdate
) -> AccountSetting:
    row = await get_settings(db, user)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return row
