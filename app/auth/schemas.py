"""Shapes for signing up, signing in, and changing your own password.

`User` itself lives in app/users/ -- this domain only owns proving who you
are, so there's no models.py here.

`role` is accepted at registration (default CANDIDATE) but ADMIN is rejected:
a self-service endpoint that accepted it would be a privilege-escalation hole.
Admins are created directly, never through this form.
"""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.users.enums import UserRole

# bcrypt's limit -- anything past this is discarded before hashing.
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LENGTH = 8


def _check_password(value: str) -> str:
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"password must be at most {MAX_PASSWORD_BYTES} bytes "
            "(shorter than that if it contains non-ASCII characters)"
        )
    return value


class UserCreate(BaseModel):
    email: EmailStr = Field(..., max_length=320)
    username: str = Field(
        ..., min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_]+$",
        description="Letters, digits and underscores. Stored lowercased.",
    )
    password: str
    full_name: str = Field(..., min_length=1, max_length=200)
    role: UserRole = UserRole.CANDIDATE
    accepted_terms: bool = Field(
        ..., description="Must be true. The consent is recorded on the account."
    )

    @field_validator("username")
    @classmethod
    def _handle(cls, value: str) -> str:
        lowered = value.strip().lower()
        # Reserved so a username can never collide with a route segment
        # like /users/me if handles end up in URLs.
        if lowered in {"me", "admin", "api", "auth", "users", "jobs", "new", "null", "undefined"}:
            raise ValueError("that username is reserved")
        return lowered

    @field_validator("accepted_terms")
    @classmethod
    def _must_accept(cls, value: bool) -> bool:
        if not value:
            raise ValueError("the terms of service must be accepted")
        return value

    @field_validator("password")
    @classmethod
    def _password(cls, value: str) -> str:
        return _check_password(value)

    @field_validator("role")
    @classmethod
    def _not_admin(cls, value: UserRole) -> UserRole:
        if value == UserRole.ADMIN:
            raise ValueError("role must be 'candidate' or 'employer'")
        return value


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _password(cls, value: str) -> str:
        return _check_password(value)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1, max_length=200)


class TokenPair(Token):
    """Returned by /auth/login and /auth/refresh. The refresh token rotates
    on every use -- store the new one, the previous value stops working."""

    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., max_length=320)


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=200)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _password(cls, value: str) -> str:
        return _check_password(value)
