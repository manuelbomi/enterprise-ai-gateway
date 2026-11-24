# ============================================================
# app/schemas/auth.py — Pydantic Schemas for Authentication
#
# ARCHITECT'S NOTE:
#   Schemas (Pydantic models) are the data contracts between the
#   API layer and the client. They are NOT the same as SQLAlchemy
#   ORM models:
#     - ORM models = database table structure
#     - Schemas = request/response shape
#   This separation prevents accidentally exposing DB internals
#   (e.g., hashed_password, litellm_virtual_key) in API responses.
# ============================================================

from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from uuid import UUID


class LoginRequest(BaseModel):
    """Body of POST /auth/login"""
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Password cannot be empty")
        return v


class TokenResponse(BaseModel):
    """Returned on successful login"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int           # seconds until access token expires


class RefreshRequest(BaseModel):
    """Body of POST /auth/refresh"""
    refresh_token: str


class TokenData(BaseModel):
    """
    Data extracted from a decoded JWT.
    This is what our auth middleware passes to route handlers —
    not the raw User ORM object, to avoid unnecessary DB queries
    on every authenticated request.
    """
    user_id: str
    role: Optional[str] = None
    team_id: Optional[str] = None


class UserPublic(BaseModel):
    """Safe user representation — never includes hashed_password or virtual keys"""
    id: UUID
    email: str
    full_name: str
    role: str
    team_id: Optional[UUID] = None
    is_active: bool

    model_config = {"from_attributes": True}  # allow creating from ORM objects


class RegisterRequest(BaseModel):
    """Body of POST /auth/register (admin-only endpoint)"""
    email: EmailStr
    full_name: str
    password: str
    role: str = "member"
    team_id: Optional[UUID] = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v
