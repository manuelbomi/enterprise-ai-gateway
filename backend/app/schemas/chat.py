# ============================================================
# app/schemas/chat.py — Chat Request/Response Schemas
# ============================================================

from pydantic import BaseModel, field_validator
from typing import List, Optional
from uuid import UUID
from datetime import datetime


class ChatMessage(BaseModel):
    """A single message in a conversation (OpenAI-compatible format)"""
    role: str           # "user" | "assistant" | "system"
    content: str

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: str) -> str:
        if v not in ("user", "assistant", "system"):
            raise ValueError(f"Invalid role: {v}. Must be user, assistant, or system.")
        return v


class ChatRequest(BaseModel):
    """
    Body of POST /chat/completions

    ARCHITECT'S NOTE:
      We deliberately keep this simple and OpenAI-compatible.
      The model field is optional — if omitted, the backend uses
      the team's default model from their ModelPolicy.
      This means users don't need to know which model to pick.
    """
    messages: List[ChatMessage]
    model: Optional[str] = None         # optional — falls back to team default
    session_id: Optional[UUID] = None   # attach to existing session, or create new
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = False                # True → returns Server-Sent Events


class ChatResponse(BaseModel):
    """Non-streaming response from POST /chat/completions"""
    session_id: UUID
    message: ChatMessage                # the assistant's reply
    model_used: str
    usage: dict                         # {prompt_tokens, completion_tokens, total_tokens}
    cost_usd: Optional[float] = None    # calculated cost for this call


class SessionSummary(BaseModel):
    """List item in GET /chat/sessions"""
    id: UUID
    title: Optional[str]
    model_used: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class SessionDetail(BaseModel):
    """Full session with messages — returned by GET /chat/sessions/{id}"""
    id: UUID
    title: Optional[str]
    messages: List[ChatMessage]
    model_used: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ModelInfo(BaseModel):
    """An available model option in the UI model selector"""
    alias: str              # e.g. "claude-haiku"
    description: str        # human-readable
    tier: str               # "economy" | "standard" | "premium"
    provider: str           # e.g. "Anthropic"
