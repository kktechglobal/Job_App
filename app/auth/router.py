"""Sign-up, sign-in, sign-out."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service
from app.auth.schemas import (
    ForgotPasswordRequest,
    PasswordChange,
    RefreshRequest,
    ResetPasswordRequest,
    Token,
    TokenPair,
    UserCreate,
)
from app.config import settings
from app.auth.dependencies import get_current_user
from app.auth.security import create_access_token
from app.database.db import get_session as get_db
from app.users.models import User
from app.users.schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _access_token(user: User) -> str:
    # `tv` lets logout and password changes invalidate tokens already issued.
    return create_access_token(
        {"sub": user.email, "role": user.role.value, "tv": user.token_version}
    )


def issue_token(user: User) -> Token:
    return Token(
        access_token=_access_token(user),
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def issue_pair(user: User, refresh_token: str) -> TokenPair:
    return TokenPair(
        access_token=_access_token(user),
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token=refresh_token,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """Create a candidate or employer account. `role` may not be `admin`."""
    return await service.register(db, user_in)


@router.post("/login", response_model=TokenPair)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """OAuth2 password flow: the email goes in the form's `username` field."""
    user = await service.authenticate(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    refresh = await service.issue_refresh_token(db, user)
    return issue_pair(user, refresh)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Exchanges a refresh token for a new pair. The token sent is consumed;
    replaying a spent one ends every session on the account."""
    user, replacement = await service.rotate_refresh_token(db, body.refresh_token)
    return issue_pair(user, replacement)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Same record as GET /users/me; kept here too since resolving a token
    to an identity is the path most auth clients reach for first."""
    return current_user


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Always returns 202, registered address or not."""
    await service.request_password_reset(db, body.email)
    return {"message": "If that address has an account, a reset link is on its way."}


@router.post("/reset-password", response_model=TokenPair)
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Single-use token from the reset email. Succeeding signs out every
    other session and returns a fresh pair."""
    user = await service.reset_password(db, body.token, body.new_password)
    refresh = await service.issue_refresh_token(db, user)
    return issue_pair(user, refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Signs out everywhere, not just this device."""
    await service.logout(db, current_user)


@router.post("/change-password", response_model=Token)
async def change_password(
    data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns a fresh token; the one used to call this is invalidated,
    including on other devices."""
    user = await service.change_password(db, current_user, data)
    return issue_token(user)
