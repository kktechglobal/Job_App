"""Who is calling, and are they allowed to.

Every rejection returns the same 401 message -- a token that says why it was
refused could be used to probe which accounts exist.
"""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.security import decode_access_token
from app.database.db import get_session as get_db
from app.exceptions import UnauthorizedAccessException
from app.users.models import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise credentials_exception

    email = payload.get("sub")
    if not email:
        raise credentials_exception

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception

    # is_active and tv catch a deactivated account or a logged-out/rotated
    # token that JWT verification alone would still accept.
    if not user.is_active:
        raise credentials_exception
    if payload.get("tv") != user.token_version:
        raise credentials_exception

    return user


def require_role(required_role: UserRole):
    """Strict equality -- ADMIN must not silently inherit candidate/employer
    routes via a subset check."""

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != required_role:
            raise UnauthorizedAccessException(
                f"Operation requires {required_role.value} privileges."
            )
        return current_user

    return role_checker
