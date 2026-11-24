# ============================================================
# app/api/auth.py — Authentication Endpoints
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.database import get_db
from app.schemas.auth import LoginRequest, TokenResponse, RegisterRequest, UserPublic, RefreshRequest
from app.services.auth_service import (
    authenticate_user, create_access_token, create_refresh_token,
    hash_password, get_user_by_id
)
from app.models.user import User, UserRole
from app.middleware.auth import get_current_user, require_super_admin
from app.schemas.auth import TokenData
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate a user and return JWT tokens.

    Flow:
      1. Validate email + password against the database
      2. Update last_login_at timestamp
      3. Return access_token (short-lived) + refresh_token (long-lived)

    The client stores both tokens and uses access_token for API calls.
    When access_token expires, the client calls /auth/refresh with the
    refresh_token to get a new access_token without re-login.
    """
    user = await authenticate_user(db, body.email, body.password)

    if not user:
        # Intentionally vague — don't tell attacker whether email or password was wrong
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Update last login timestamp for audit trail
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    access_token = create_access_token(
        user_id=user.id,
        role=user.role,
        team_id=user.team_id,
    )
    refresh_token = create_refresh_token(user_id=user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register_user(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    _admin: TokenData = Depends(require_super_admin),   # only super_admin can create users
):
    """
    Create a new user. Super admin only.

    ARCHITECT'S NOTE:
      In a typical enterprise deployment, user creation is done by IT admins,
      not via self-registration. This endpoint is called by the Admin panel
      when onboarding a new employee.
      After creating the user, the admin would also call /teams/assign-user
      to place them in the correct team (which triggers LiteLLM key generation).
    """
    from sqlalchemy import select
    # Check for duplicate email
    existing = await db.execute(
        select(User).where(User.email == body.email.lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with email {body.email} already exists",
        )

    new_user = User(
        email=body.email.lower(),
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=UserRole(body.role),
        team_id=body.team_id,
    )
    db.add(new_user)
    await db.flush()    # flush to get the generated UUID without committing

    return new_user


@router.get("/me", response_model=UserPublic)
async def get_me(
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
):
    """Return the authenticated user's profile. Called on app load to verify token."""
    from uuid import UUID
    user = await get_user_by_id(db, UUID(token_data.user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
