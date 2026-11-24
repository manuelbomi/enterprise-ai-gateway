# ============================================================
# app/models/team.py — Team & ModelPolicy ORM Models
#
# ARCHITECT'S NOTE:
#   This is the core of the enterprise multi-tenancy model.
#
#   TEAM = Department (HR, Engineering, Logistics, C-Suite, etc.)
#
#   Each team has a ModelPolicy that defines:
#     - Which LLM models team members are allowed to use
#     - Monthly spend budget (USD)
#     - Request rate limits (RPM/TPM)
#
#   When a user sends a chat message, the backend checks their
#   team's ModelPolicy and routes to the correct LiteLLM virtual
#   key with the right budget and model restrictions.
#
#   This maps directly to LiteLLM's /team/new and /key/generate
#   proxy management APIs.
# ============================================================

from sqlalchemy import (
    Column, String, Boolean, DateTime, Float,
    Integer, ForeignKey, ARRAY, func, Text
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.database import Base


class Team(Base):
    """
    Represents a department or business unit in the enterprise.
    Examples: "HR", "Engineering", "Logistics", "C-Suite"
    """
    __tablename__ = "teams"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(255), unique=True, nullable=False)       # e.g. "HR Team"
    slug = Column(String(100), unique=True, nullable=False)       # e.g. "hr-team" (URL-safe)
    description = Column(Text, nullable=True)

    # LiteLLM assigns a team ID when we create the team via proxy API.
    # We store it here to link our teams table to LiteLLM's internal records.
    litellm_team_id = Column(String(255), nullable=True, unique=True)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # -------------------------------------------------------
    # Relationships
    # -------------------------------------------------------
    members = relationship("User", back_populates="team")
    policy = relationship("ModelPolicy", back_populates="team", uselist=False, cascade="all, delete-orphan")
    usage_logs = relationship("UsageLog", back_populates="team")

    def __repr__(self) -> str:
        return f"<Team {self.name}>"


class ModelPolicy(Base):
    """
    Defines what AI capabilities a team is allowed to use.

    ARCHITECT'S NOTE:
      This is the enterprise governance layer. It answers:
        - "Can the HR team use GPT-4o?" → check allowed_models
        - "Has Engineering hit their monthly budget?" → check spend_limit_usd
        - "Is Logistics being rate-limited?" → check rpm_limit

      These values are synced to LiteLLM's virtual key settings when
      the policy is created or updated, so enforcement happens at the
      proxy level — not just in our application code.
    """
    __tablename__ = "model_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, unique=True)

    # List of model aliases the team can use (from litellm/config.yaml model_name)
    # e.g. ["claude-haiku", "gpt-4o-mini"]
    # Stored as a PostgreSQL array — easily queryable
    allowed_models = Column(ARRAY(String), nullable=False, default=list)

    # Default model used when the user doesn't specify one
    default_model = Column(String(100), nullable=False, default="claude-haiku")

    # Monthly budget in USD — LiteLLM enforces this at the proxy level
    spend_limit_usd = Column(Float, nullable=False, default=100.0)

    # Rate limits — requests and tokens per minute
    # LiteLLM will return 429 when these are exceeded
    rpm_limit = Column(Integer, nullable=False, default=100)   # requests/min
    tpm_limit = Column(Integer, nullable=False, default=100000) # tokens/min

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship back to Team
    team = relationship("Team", back_populates="policy")

    def __repr__(self) -> str:
        return f"<ModelPolicy team={self.team_id} models={self.allowed_models}>"
