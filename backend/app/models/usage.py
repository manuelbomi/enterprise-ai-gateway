# ============================================================
# app/models/usage.py — Chat Session & Usage Tracking Models
#
# ARCHITECT'S NOTE:
#   Usage tracking is non-negotiable in enterprise AI.
#   Finance needs cost attribution per department.
#   Security needs an audit trail.
#   Engineering needs latency and error data for SLA reporting.
#
#   We store two levels of data:
#     1. ChatSession — a conversation thread (many messages)
#     2. UsageLog    — one record per LLM API call with
#                      token counts, cost, latency, model used
#
#   LiteLLM also keeps its own spend_logs in Postgres, but we
#   maintain our own UsageLog for richer application-level context
#   (which user, which session, which team, what was the purpose).
# ============================================================

from sqlalchemy import (
    Column, String, Boolean, DateTime, Float,
    Integer, ForeignKey, Text, func, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.database import Base


class ChatSession(Base):
    """
    A conversation thread — groups many messages under one context window.
    Users can have multiple sessions (similar to ChatGPT's sidebar threads).
    """
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Human-readable title — auto-generated from first message, editable by user
    title = Column(String(500), nullable=True)

    # The model used in this session (can change mid-session)
    model_used = Column(String(100), nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at")
    usage_logs = relationship("UsageLog", back_populates="session")


class Message(Base):
    """
    A single message in a chat session.
    Stores both user messages and AI responses.
    """
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)

    # "user" | "assistant" | "system"
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)

    # For assistant messages — which model generated this response?
    model_used = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")


class UsageLog(Base):
    """
    Detailed per-request usage record.

    ARCHITECT'S NOTE:
      This table drives the admin analytics dashboard.
      Key metrics captured per LLM call:
        - Exact model used (even if the user selected a generic alias)
        - Prompt + completion tokens (for cost calculation)
        - Actual cost in USD (calculated from provider pricing)
        - Latency in milliseconds (for SLA monitoring)
        - Success/failure status

      These are queryable by team, user, model, date range.
      A BI tool (Metabase, Redash, Grafana) can connect directly
      to this table for executive dashboards.
    """
    __tablename__ = "usage_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Who made the call
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True)

    # What model was actually called (the real provider model, not the alias)
    model_alias = Column(String(100), nullable=True)    # e.g. "claude-haiku" (our alias)
    model_actual = Column(String(100), nullable=True)   # e.g. "anthropic/claude-haiku-3-5"
    provider = Column(String(50), nullable=True)        # e.g. "anthropic"

    # Token usage
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)

    # Cost in USD — calculated by LiteLLM based on provider pricing tables
    cost_usd = Column(Float, nullable=True)

    # Performance
    latency_ms = Column(Integer, nullable=True)         # milliseconds to first token

    # Status
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)

    # Raw LiteLLM response metadata (useful for debugging)
    response_metadata = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    session = relationship("ChatSession", back_populates="usage_logs")
    team = relationship("Team", back_populates="usage_logs")
