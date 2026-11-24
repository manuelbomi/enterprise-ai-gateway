# ============================================================
# app/api/chat.py — Chat Completion Endpoints
#
# ARCHITECT'S NOTE:
#   This is the primary user-facing API. Every message sent from
#   the UI passes through here.
#
#   Two completion modes are supported:
#     1. Standard (non-streaming): full response returned in one JSON payload
#     2. Streaming: tokens arrive as Server-Sent Events (SSE)
#
#   The routing logic:
#     1. Load the user's team and ModelPolicy from the DB
#     2. If the user requested a model, verify their policy allows it
#     3. If no model requested, use the team's default_model
#     4. Call LiteLLM proxy with the user's virtual key
#     5. Log the usage to UsageLog for cost tracking
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from uuid import UUID
import json
import httpx

from app.database import get_db
from app.middleware.auth import get_current_user
from app.schemas.auth import TokenData
from app.schemas.chat import ChatRequest, ChatResponse, SessionSummary, SessionDetail, ChatMessage
from app.services.litellm_service import chat_completion, stream_chat_completion
from app.models.usage import ChatSession, Message, UsageLog
from app.models.user import User
from app.models.team import ModelPolicy

router = APIRouter(prefix="/chat", tags=["Chat"])


# -------------------------------------------------------
# Helper: resolve the model and virtual key for a user
# -------------------------------------------------------

async def _get_user_model_and_key(
    user_id: UUID,
    requested_model: str | None,
    db: AsyncSession,
) -> tuple[str, str]:
    """
    Determine which model to use and return the user's LiteLLM virtual key.

    Raises HTTPException if:
      - User is not assigned to a team
      - Requested model is not in the team's allowed_models list
      - User has no virtual key (admin forgot to issue one)
    """
    # Load user with their team's policy in a single query
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.team).selectinload("policy"))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.team or not user.team.policy:
        raise HTTPException(
            status_code=403,
            detail="Your account is not assigned to a team. Contact your admin.",
        )

    policy: ModelPolicy = user.team.policy

    # Determine which model to use
    if requested_model:
        if requested_model not in policy.allowed_models:
            raise HTTPException(
                status_code=403,
                detail=f"Model '{requested_model}' is not available for your team. "
                       f"Allowed: {policy.allowed_models}",
            )
        model = requested_model
    else:
        # Fall back to the team's configured default
        model = policy.default_model

    if not user.litellm_virtual_key:
        raise HTTPException(
            status_code=503,
            detail="Your account key has not been provisioned yet. Contact your admin.",
        )

    return model, user.litellm_virtual_key


# -------------------------------------------------------
# Standard (non-streaming) Chat Completion
# -------------------------------------------------------

@router.post("/completions", response_model=ChatResponse)
async def create_completion(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
):
    """
    Send a chat message and get a full response.
    Use this for most cases. Use /completions/stream for real-time token output.
    """
    user_id = UUID(token_data.user_id)
    model, virtual_key = await _get_user_model_and_key(user_id, body.model, db)

    # Retrieve or create a ChatSession for history grouping
    if body.session_id:
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.id == body.session_id,
                ChatSession.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
    else:
        session = ChatSession(user_id=user_id, model_used=model)
        db.add(session)
        await db.flush()

    # Persist the user's message
    user_message = Message(
        session_id=session.id,
        role="user",
        content=body.messages[-1].content,  # the latest user message
    )
    db.add(user_message)

    # Call LiteLLM Proxy
    try:
        raw = await chat_completion(
            messages=body.messages,
            model=model,
            virtual_key=virtual_key,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            user_id=str(user_id),
        )
    except httpx.HTTPStatusError as e:
        # Surface LiteLLM/provider errors with context
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"AI provider error: {e.response.text}",
        )

    # Parse response
    assistant_content = raw["choices"][0]["message"]["content"]
    usage_data = raw.get("usage", {})
    cost_usd = raw.get("_cost", None)       # LiteLLM injects this if spend tracking is on
    latency_ms = raw.get("_latency_ms", 0)

    # Persist assistant reply
    assistant_message = Message(
        session_id=session.id,
        role="assistant",
        content=assistant_content,
        model_used=model,
    )
    db.add(assistant_message)

    # Auto-title the session from the first user message
    if not session.title:
        session.title = body.messages[-1].content[:80]

    # Log usage for analytics
    usage_log = UsageLog(
        user_id=user_id,
        team_id=UUID(token_data.team_id) if token_data.team_id else None,
        session_id=session.id,
        model_alias=model,
        model_actual=raw.get("model"),
        prompt_tokens=usage_data.get("prompt_tokens"),
        completion_tokens=usage_data.get("completion_tokens"),
        total_tokens=usage_data.get("total_tokens"),
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        success=True,
    )
    db.add(usage_log)

    return ChatResponse(
        session_id=session.id,
        message=ChatMessage(role="assistant", content=assistant_content),
        model_used=model,
        usage=usage_data,
        cost_usd=cost_usd,
    )


# -------------------------------------------------------
# Streaming Chat Completion
# -------------------------------------------------------

@router.post("/completions/stream")
async def create_completion_stream(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
):
    """
    Stream chat completion tokens as Server-Sent Events.

    ARCHITECT'S NOTE:
      The browser connects to this endpoint and receives tokens
      in real-time as the LLM generates them.

      Client-side usage (JavaScript):
        const evtSource = new EventSource("/chat/completions/stream");
        evtSource.onmessage = (e) => {
          const data = JSON.parse(e.data);
          const token = data.choices[0].delta.content;
          appendToUI(token);
        };

      We use FastAPI's StreamingResponse with media_type="text/event-stream"
      to keep the HTTP connection open and flush chunks to the client.
    """
    user_id = UUID(token_data.user_id)
    model, virtual_key = await _get_user_model_and_key(user_id, body.model, db)

    async def event_generator():
        """Generator that pipes LiteLLM SSE chunks to the client."""
        try:
            async for chunk in stream_chat_completion(
                messages=body.messages,
                model=model,
                virtual_key=virtual_key,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
            ):
                yield chunk
        except httpx.HTTPStatusError as e:
            # Send error as a final SSE event so the client knows why streaming stopped
            error_event = f"data: {json.dumps({'error': e.response.text})}\n\n"
            yield error_event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",    # disable nginx buffering for streaming
        },
    )


# -------------------------------------------------------
# Session Management
# -------------------------------------------------------

@router.get("/sessions", response_model=List[SessionSummary])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
):
    """Return all chat sessions for the authenticated user (newest first)."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == UUID(token_data.user_id))
        .order_by(ChatSession.updated_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
):
    """Load a specific chat session with all its messages."""
    result = await db.execute(
        select(ChatSession)
        .where(
            ChatSession.id == session_id,
            ChatSession.user_id == UUID(token_data.user_id),
        )
        .options(selectinload(ChatSession.messages))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionDetail(
        id=session.id,
        title=session.title,
        messages=[ChatMessage(role=m.role, content=m.content) for m in session.messages],
        model_used=session.model_used,
        created_at=session.created_at,
    )
