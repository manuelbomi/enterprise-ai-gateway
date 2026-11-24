# ============================================================
# app/services/auth_service.py — Authentication Business Logic
#
# ARCHITECT'S NOTE:
#   This service owns all security-sensitive operations:
#     - Password hashing and verification
#     - JWT token creation and validation
#     - User lookup and session management
#
#   We use bcrypt for password hashing (industry standard — slow by design
#   to defeat brute-force attacks) and JWTs for stateless auth.
#
#   STATELESS JWT design: We do NOT store sessions in the DB.
#   The token itself carries the user's identity and role.
#   This scales horizontally with no sticky-session requirements.
#   Downside: tokens cannot be instantly revoked (use short expiry + refresh tokens).
# ============================================================

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User, UserRole
from app.schemas.auth import TokenData


# -------------------------------------------------------
# Password Hashing
# CryptContext auto-detects the hash algorithm and handles
# future algorithm migrations gracefully (deprecated= warns
# when an old hash is encountered).
# -------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt. Store the result, not the original."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compare a plaintext password against a stored bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


# -------------------------------------------------------
# JWT Token Management
# -------------------------------------------------------

def create_access_token(user_id: UUID, role: UserRole, team_id: Optional[UUID] = None) -> str:
    """
    Create a signed JWT access token.

    The payload ('claims') includes:
      sub   — subject: the user's UUID (standard JWT claim)
      role  — the user's role for RBAC checks without a DB hit
      team  — the user's team UUID (for model routing decisions)
      exp   — expiry timestamp (standard JWT claim)
      type  — "access" so we can distinguish from refresh tokens
    """
    expiry = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )

    payload = {
        "sub": str(user_id),
        "role": role.value,
        "team": str(team_id) if team_id else None,
        "exp": expiry,
        "type": "access",
    }

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: UUID) -> str:
    """
    Create a longer-lived refresh token.
    Used to obtain a new access token without re-login.
    Store refresh tokens server-side (Redis) for revocation support.
    """
    expiry = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_token_expire_days
    )

    payload = {
        "sub": str(user_id),
        "exp": expiry,
        "type": "refresh",
    }

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[TokenData]:
    """
    Validate and decode a JWT access token.
    Returns None if the token is invalid, expired, or tampered with.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        user_id: str = payload.get("sub")
        role: str = payload.get("role")
        team_id: str = payload.get("team")
        token_type: str = payload.get("type")

        if not user_id or token_type != "access":
            return None

        return TokenData(user_id=user_id, role=role, team_id=team_id)

    except JWTError:
        # Catches: expired, invalid signature, malformed token
        return None


# -------------------------------------------------------
# User Lookup
# -------------------------------------------------------

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Fetch a user by email. Returns None if not found."""
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> Optional[User]:
    """Fetch a user by UUID primary key."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    """
    Validate email + password and return the User if correct.
    Returns None for invalid credentials (never reveal WHICH part was wrong —
    that leaks whether the email exists, which is a security risk).
    """
    user = await get_user_by_email(db, email)
    if not user:
        # Still run the hash to prevent timing attacks that could
        # determine whether an email exists based on response time
        pwd_context.dummy_verify()
        return None

    if not verify_password(password, user.hashed_password):
        return None

    if not user.is_active:
        return None

    return user
