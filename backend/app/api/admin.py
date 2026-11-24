# ============================================================
# app/api/admin.py — Admin Dashboard Endpoints
#
# ARCHITECT'S NOTE:
#   These endpoints power the Admin Panel in the UI.
#   Only super_admin users can call them.
#
#   Key capabilities:
#     - Team CRUD (create/update/delete departments)
#     - Model policy management (control which team gets which models)
#     - Usage analytics (cost per team, top users, model breakdown)
#     - User management (activate/deactivate, reassign teams)
#
#   These are the endpoints an AI Architect would demo to the
#   CTO/CISO when presenting the enterprise governance story:
#   "Every API call is tracked, budgeted, and attributable."
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

from app.database import get_db
from app.middleware.auth import require_super_admin, require_team_admin
from app.schemas.auth import TokenData, UserPublic
from app.models.team import Team, ModelPolicy
from app.models.user import User, UserRole
from app.models.usage import UsageLog
from app.services.litellm_service import (
    create_team_in_litellm, create_virtual_key, get_team_spend
)

router = APIRouter(prefix="/admin", tags=["Admin"])


# -------------------------------------------------------
# Request/Response Schemas (defined inline for clarity)
# -------------------------------------------------------

class CreateTeamRequest(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    allowed_models: List[str]
    default_model: str
    spend_limit_usd: float = 100.0
    rpm_limit: int = 100


class TeamResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: Optional[str]
    is_active: bool
    member_count: Optional[int] = 0

    model_config = {"from_attributes": True}


class UsageSummary(BaseModel):
    team_name: str
    total_calls: int
    total_tokens: int
    total_cost_usd: float
    top_model: Optional[str]


# -------------------------------------------------------
# Team Management
# -------------------------------------------------------

@router.post("/teams", response_model=TeamResponse, status_code=201)
async def create_team(
    body: CreateTeamRequest,
    db: AsyncSession = Depends(get_db),
    _admin: TokenData = Depends(require_super_admin),
):
    """
    Create a new department team and provision it in LiteLLM.

    Flow:
      1. Create Team row in our DB
      2. Create ModelPolicy row (which models, budget, rate limits)
      3. Register the team in LiteLLM proxy (/team/new)
      4. Store the LiteLLM team ID back in our teams table
    """
    team = Team(name=body.name, slug=body.slug, description=body.description)
    db.add(team)
    await db.flush()    # get UUID before commit

    policy = ModelPolicy(
        team_id=team.id,
        allowed_models=body.allowed_models,
        default_model=body.default_model,
        spend_limit_usd=body.spend_limit_usd,
        rpm_limit=body.rpm_limit,
    )
    db.add(policy)
    await db.flush()

    # Register team in LiteLLM proxy so budgets are enforced at the proxy layer
    try:
        litellm_response = await create_team_in_litellm(
            team_name=body.name,
            team_id=str(team.id),
            budget_usd=body.spend_limit_usd,
            models=body.allowed_models,
        )
        team.litellm_team_id = litellm_response.get("team_id", str(team.id))
    except Exception as e:
        # Don't fail team creation if LiteLLM sync fails — log it and continue.
        # The admin can re-sync manually. The app still works; budgets just
        # won't be enforced at proxy level until sync succeeds.
        print(f"[WARNING] LiteLLM team sync failed: {e}")

    return team


@router.get("/teams", response_model=List[TeamResponse])
async def list_teams(
    db: AsyncSession = Depends(get_db),
    _admin: TokenData = Depends(require_team_admin),
):
    """List all teams. Team admins see all teams (they may manage multiple)."""
    result = await db.execute(select(Team).options(selectinload(Team.members)))
    teams = result.scalars().all()

    # Attach member count
    return [
        TeamResponse(
            id=t.id,
            name=t.name,
            slug=t.slug,
            description=t.description,
            is_active=t.is_active,
            member_count=len(t.members),
        )
        for t in teams
    ]


@router.post("/teams/{team_id}/assign-user")
async def assign_user_to_team(
    team_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: TokenData = Depends(require_super_admin),
):
    """
    Assign a user to a team and provision their LiteLLM virtual key.

    ARCHITECT'S NOTE:
      This is the user onboarding workflow:
        1. Super admin creates the user (/auth/register)
        2. Super admin calls this endpoint to assign them to a team
        3. We generate their LiteLLM virtual key with the team's model/budget policy
        4. The user can now log in and immediately start using AI
    """
    # Load team with policy
    result = await db.execute(
        select(Team).where(Team.id == team_id).options(selectinload(Team.policy))
    )
    team = result.scalar_one_or_none()
    if not team or not team.policy:
        raise HTTPException(status_code=404, detail="Team not found or has no policy")

    # Load user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Assign team
    user.team_id = team_id

    # Generate LiteLLM virtual key for this user
    try:
        virtual_key = await create_virtual_key(
            user_id=str(user_id),
            team_id=str(team_id),
            models=team.policy.allowed_models,
            spend_limit_usd=team.policy.spend_limit_usd,
            rpm_limit=team.policy.rpm_limit,
        )
        user.litellm_virtual_key = virtual_key
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to provision AI key: {e}")

    return {"message": f"User {user.email} assigned to {team.name}", "team_id": str(team_id)}


# -------------------------------------------------------
# Usage Analytics — powers the admin dashboard charts
# -------------------------------------------------------

@router.get("/analytics/usage-by-team", response_model=List[UsageSummary])
async def usage_by_team(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    _admin: TokenData = Depends(require_team_admin),
):
    """
    Aggregate cost and usage statistics per team for the last N days.
    Used to render the department cost breakdown chart on the admin dashboard.
    """
    from datetime import datetime, timedelta, timezone
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            Team.name,
            func.count(UsageLog.id).label("total_calls"),
            func.sum(UsageLog.total_tokens).label("total_tokens"),
            func.sum(UsageLog.cost_usd).label("total_cost_usd"),
            func.mode().within_group(UsageLog.model_alias.asc()).label("top_model"),
        )
        .join(UsageLog, UsageLog.team_id == Team.id)
        .where(UsageLog.created_at >= since)
        .group_by(Team.name)
        .order_by(desc("total_cost_usd"))
    )

    rows = result.all()
    return [
        UsageSummary(
            team_name=row.name,
            total_calls=row.total_calls or 0,
            total_tokens=row.total_tokens or 0,
            total_cost_usd=round(row.total_cost_usd or 0, 4),
            top_model=row.top_model,
        )
        for row in rows
    ]


@router.get("/analytics/daily-cost")
async def daily_cost(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    _admin: TokenData = Depends(require_super_admin),
):
    """Daily spend across all teams — used for the cost trend line chart."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import cast, Date

    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            cast(UsageLog.created_at, Date).label("date"),
            func.sum(UsageLog.cost_usd).label("cost_usd"),
            func.count(UsageLog.id).label("calls"),
        )
        .where(UsageLog.created_at >= since, UsageLog.success == True)
        .group_by("date")
        .order_by("date")
    )

    return [
        {"date": str(row.date), "cost_usd": round(row.cost_usd or 0, 4), "calls": row.calls}
        for row in result.all()
    ]


@router.get("/analytics/usage-by-user")
async def usage_by_user(
    days: int = 30,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _admin: TokenData = Depends(require_team_admin),
):
    """
    Top users by spend for the last N days.
    Used by the enterprise-ai-monitor companion dashboard's "Cost by User" view.
    Helps identify runaway usage early before budgets are exceeded.
    """
    from datetime import datetime, timedelta, timezone
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            User.full_name,
            User.email,
            Team.name.label("team_name"),
            func.count(UsageLog.id).label("total_calls"),
            func.sum(UsageLog.total_tokens).label("total_tokens"),
            func.sum(UsageLog.cost_usd).label("total_cost_usd"),
            func.avg(UsageLog.latency_ms).label("avg_latency_ms"),
        )
        .join(UsageLog, UsageLog.user_id == User.id)
        .outerjoin(Team, Team.id == User.team_id)
        .where(UsageLog.created_at >= since, UsageLog.success == True)
        .group_by(User.full_name, User.email, Team.name)
        .order_by(desc("total_cost_usd"))
        .limit(limit)
    )

    return [
        {
            "full_name": row.full_name,
            "email": row.email,
            "team_name": row.team_name or "Unassigned",
            "total_calls": row.total_calls or 0,
            "total_tokens": row.total_tokens or 0,
            "total_cost_usd": round(row.total_cost_usd or 0, 4),
            "avg_latency_ms": round(row.avg_latency_ms or 0),
        }
        for row in result.all()
    ]


@router.get("/analytics/usage-by-model")
async def usage_by_model(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    _admin: TokenData = Depends(require_team_admin),
):
    """
    Cost and usage breakdown by model alias.
    Shows which LLM is being used most and what it costs.
    Used by the "Cost by Model" view in the monitoring dashboard.
    """
    from datetime import datetime, timedelta, timezone
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            UsageLog.model_alias,
            UsageLog.model_actual,
            func.count(UsageLog.id).label("call_count"),
            func.sum(UsageLog.total_tokens).label("total_tokens"),
            func.sum(UsageLog.prompt_tokens).label("prompt_tokens"),
            func.sum(UsageLog.completion_tokens).label("completion_tokens"),
            func.sum(UsageLog.cost_usd).label("total_cost_usd"),
            func.avg(UsageLog.latency_ms).label("avg_latency_ms"),
        )
        .where(UsageLog.created_at >= since, UsageLog.success == True)
        .group_by(UsageLog.model_alias, UsageLog.model_actual)
        .order_by(desc("total_cost_usd"))
    )

    return [
        {
            "model_alias": row.model_alias or "unknown",
            "model_actual": row.model_actual or "unknown",
            "call_count": row.call_count or 0,
            "total_tokens": row.total_tokens or 0,
            "prompt_tokens": row.prompt_tokens or 0,
            "completion_tokens": row.completion_tokens or 0,
            "total_cost_usd": round(row.total_cost_usd or 0, 4),
            "avg_latency_ms": round(row.avg_latency_ms or 0),
        }
        for row in result.all()
    ]


@router.get("/analytics/budget-status")
async def budget_status(
    db: AsyncSession = Depends(get_db),
    _admin: TokenData = Depends(require_team_admin),
):
    """
    Current-month budget utilisation per team.
    Returns remaining budget, % used, and a RAG status (green/amber/red).
    Used by the "Budget Status" view in the monitoring dashboard to alert
    admins before a team hits their monthly limit.

    RAG thresholds:
      green  — under 70% of budget used
      amber  — 70–90% used (warn the team)
      red    — over 90% used (action required)
    """
    from datetime import datetime, timezone
    from sqlalchemy.orm import selectinload

    month_start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    result = await db.execute(
        select(
            Team.id,
            Team.name,
            ModelPolicy.spend_limit_usd,
            func.coalesce(func.sum(UsageLog.cost_usd), 0).label("spent_usd"),
            func.coalesce(func.count(UsageLog.id), 0).label("calls_this_month"),
        )
        .join(ModelPolicy, ModelPolicy.team_id == Team.id)
        .outerjoin(
            UsageLog,
            (UsageLog.team_id == Team.id) & (UsageLog.created_at >= month_start)
        )
        .where(Team.is_active == True)
        .group_by(Team.id, Team.name, ModelPolicy.spend_limit_usd)
        .order_by(desc("spent_usd"))
    )

    rows = result.all()
    statuses = []
    for row in rows:
        pct = (row.spent_usd / row.spend_limit_usd * 100) if row.spend_limit_usd else 0
        if pct >= 90:
            rag = "red"
        elif pct >= 70:
            rag = "amber"
        else:
            rag = "green"

        statuses.append({
            "team_id": str(row.id),
            "team_name": row.name,
            "budget_usd": row.spend_limit_usd,
            "spent_usd": round(row.spent_usd, 4),
            "remaining_usd": round(max(row.spend_limit_usd - row.spent_usd, 0), 4),
            "pct_used": round(pct, 1),
            "calls_this_month": row.calls_this_month,
            "rag_status": rag,
        })

    return statuses


@router.get("/analytics/weekly-summary")
async def weekly_summary(
    weeks: int = 4,
    db: AsyncSession = Depends(get_db),
    _admin: TokenData = Depends(require_super_admin),
):
    """
    Week-by-week cost and usage summary across all teams.
    Returns the last N weeks of data for the trend chart in the monitoring dashboard.
    Also used to generate the printable weekly report for leadership.
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import cast, Date, extract

    since = datetime.now(timezone.utc) - timedelta(weeks=weeks)

    result = await db.execute(
        select(
            Team.name.label("team_name"),
            func.date_trunc("week", UsageLog.created_at).label("week_start"),
            func.sum(UsageLog.cost_usd).label("cost_usd"),
            func.sum(UsageLog.total_tokens).label("total_tokens"),
            func.count(UsageLog.id).label("calls"),
        )
        .join(Team, Team.id == UsageLog.team_id)
        .where(UsageLog.created_at >= since, UsageLog.success == True)
        .group_by(Team.name, "week_start")
        .order_by("week_start", Team.name)
    )

    return [
        {
            "team_name": row.team_name,
            "week_start": str(row.week_start)[:10],  # YYYY-MM-DD
            "cost_usd": round(row.cost_usd or 0, 4),
            "total_tokens": row.total_tokens or 0,
            "calls": row.calls or 0,
        }
        for row in result.all()
    ]
