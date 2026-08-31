"""Registration, sign-in, and password changes.

Failed logins always say "incorrect email or password" regardless of which
half was wrong, so the endpoint can't be used to enumerate accounts.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import PasswordResetToken, RefreshToken
from app.auth.schemas import PasswordChange, UserCreate
from app.auth.security import generate_token, hash_password, hash_token, verify_password
from app.config import settings
from app.exceptions import DuplicateResourceException, InvalidOperationException
from app.notifications import service as notifications_service
from app.notifications.schemas import NotificationCreate
from app.users.models import User


def _aware(value: datetime) -> datetime:
    """SQLite returns naive datetimes; Postgres returns tz-aware ones. Values
    are always written as UTC, so a naive one is treated as UTC here."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


async def register(db: AsyncSession, user_in: UserCreate) -> User:
    email = user_in.email.lower()

    existing = await db.execute(select(User.id).where(User.email == email))
    if existing.first():
        raise DuplicateResourceException("Email already registered.")

    taken = await db.execute(select(User.id).where(User.username == user_in.username))
    if taken.first():
        raise DuplicateResourceException("That username is taken.")

    user = User(
        email=email,
        username=user_in.username,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role,
        accepted_terms_at=datetime.now(timezone.utc),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        # Handles the race between the uniqueness checks above and the commit.
        await db.rollback()
        raise DuplicateResourceException(
            "That email or username is already registered."
        ) from exc

    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> Optional[User]:
    """None for every failure mode, so a caller can't distinguish an unknown
    email from a wrong password from a disabled account."""
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalars().first()

    if user is None:
        # Hash anyway -- an early return here would be measurably faster and
        # would leak which emails are registered via timing.
        verify_password(password, "$2b$12$" + "x" * 53)
        return None

    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


async def change_password(db: AsyncSession, user: User, data: PasswordChange) -> User:
    if not verify_password(data.current_password, user.hashed_password):
        raise InvalidOperationException("Current password is incorrect.")
    if data.current_password == data.new_password:
        raise InvalidOperationException("New password must differ from the current one.")

    user.hashed_password = hash_password(data.new_password)
    # token_version bump invalidates already-issued access tokens; revoking
    # refresh rows stops them from minting new ones.
    user.token_version += 1
    await _revoke_all(db, user.id)

    await db.commit()
    await db.refresh(user)
    return user


async def logout(db: AsyncSession, user: User) -> None:
    """Signs out every session, not just the caller's. Per-device logout
    would need each refresh token tied to a device."""
    user.token_version += 1
    await _revoke_all(db, user.id)
    await db.commit()

# ------------------------------------------------------- refresh tokens


async def issue_refresh_token(db: AsyncSession, user: User) -> str:
    """Mints one and returns the raw value; only its hash is stored."""
    raw = generate_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        expires_at=datetime.now(timezone.utc)
                   + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    ))
    await db.commit()
    return raw


async def _revoke_all(db: AsyncSession, user_id: int) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )


async def rotate_refresh_token(db: AsyncSession, raw: str) -> Tuple[User, str]:
    """Exchanges a refresh token for a new pair. Every failure raises the
    same error so a caller can't distinguish unknown/expired/revoked."""
    rejected = InvalidOperationException("Invalid or expired refresh token.")

    row = (await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw))
    )).scalars().first()
    if row is None:
        raise rejected

    now = datetime.now(timezone.utc)

    if row.used_at is not None:
        # Reuse of an already-exchanged token means theft -- revoke the whole chain.
        await _revoke_all(db, row.user_id)
        user = (await db.execute(
            select(User).where(User.id == row.user_id)
        )).scalars().first()
        if user is not None:
            user.token_version += 1
        await db.commit()
        raise rejected

    if row.revoked_at is not None or _aware(row.expires_at) <= now:
        raise rejected

    user = (await db.execute(select(User).where(User.id == row.user_id))).scalars().first()
    if user is None or not user.is_active:
        raise rejected

    replacement = generate_token()
    new_row = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(replacement),
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(new_row)
    await db.flush()

    row.used_at = now
    row.replaced_by = new_row.id

    await db.commit()
    await db.refresh(user)
    return user, replacement

# ------------------------------------------------------ password reset


async def request_password_reset(db: AsyncSession, email: str) -> None:
    """Always succeeds whether or not the address is registered, so the
    response can't be used to check who has an account."""
    user = (await db.execute(
        select(User).where(User.email == email.lower())
    )).scalars().first()

    if user is None or not user.is_active:
        return

    raw = generate_token()
    db.add(PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        expires_at=datetime.now(timezone.utc)
                   + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES),
    ))

    await notifications_service.queue(db, NotificationCreate(
        user_id=user.id,
        subject="Reset your password",
        body=(
            f"Open {settings.FRONTEND_RESET_URL}?token={raw} to choose a new "
            f"password. The link stops working in "
            f"{settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes."
        ),
    ))
    await db.commit()


async def reset_password(db: AsyncSession, raw: str, new_password: str) -> User:
    rejected = InvalidOperationException("Invalid or expired reset token.")

    row = (await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(raw))
    )).scalars().first()
    if row is None or row.used_at is not None:
        raise rejected

    now = datetime.now(timezone.utc)
    if _aware(row.expires_at) <= now:
        raise rejected

    user = (await db.execute(select(User).where(User.id == row.user_id))).scalars().first()
    if user is None or not user.is_active:
        raise rejected

    user.hashed_password = hash_password(new_password)
    # A compromised session may be what prompted the reset -- end all of them.
    user.token_version += 1
    await _revoke_all(db, user.id)
    row.used_at = now

    await db.commit()
    await db.refresh(user)
    return user
