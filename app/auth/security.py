"""Password hashing and access tokens.

Uses bcrypt directly rather than passlib: passlib reads
`bcrypt.__about__.__version__`, removed in bcrypt 4.1+, and then rejects every
password as "too long" regardless of its actual length. passlib has had no
release since 2020. app/requirements.txt pins bcrypt==4.0.1 to dodge this; the
root requirements.txt (a stale pip freeze) pins 5.0.0 and re-triggers it, so
which file you installed from decided whether registration worked at all.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt

from app.config import settings

# bcrypt hashes only the first 72 bytes and silently drops the rest; keep
# this in sync with the length check in app/users/schemas.py.
MAX_PASSWORD_BYTES = 72

# Prevents a refresh or password-reset token from being replayed here as an
# access token.
TOKEN_TYPE = "access"


def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError(f"password must be at most {MAX_PASSWORD_BYTES} bytes")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


# Old name, kept because other modules still import it.
get_password_hash = hash_password


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """False for every failure mode -- a malformed hash or an over-length
    password is a failed login, not a 500."""
    try:
        encoded = plain_password.encode("utf-8")
        if len(encoded) > MAX_PASSWORD_BYTES:
            return False
        return bcrypt.checkpw(encoded, hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    data: dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": now, "type": TOKEN_TYPE})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Raises jwt.PyJWTError if the token is invalid, expired, or not ours."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    if payload.get("type") != TOKEN_TYPE:
        raise jwt.InvalidTokenError("not an access token")
    return payload


# ---------------------------------------------------------------- opaque tokens

def generate_token() -> str:
    """Refresh and password-reset tokens are opaque random strings, not
    JWTs -- rotation and revocation need a database lookup either way, so a
    JWT would only add its own claims for someone to read."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """SHA-256, not bcrypt: these are already 384 bits of randomness with
    nothing to brute-force, so a fast digest is fine and is what allows
    looking a token up by its hash. Only the hash is stored."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
