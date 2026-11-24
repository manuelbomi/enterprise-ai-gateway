# ============================================================
# app/services/litellm_service.py — LiteLLM Integration Layer
#
# ARCHITECT'S NOTE:
#   This is the most important service in the entire platform.
#   It encapsulates all communication with the LiteLLM Proxy.
#
#   DESIGN DECISION — Why talk to LiteLLM Proxy instead of calling
#   LiteLLM library directly?
#
#     Proxy approach (what we do here):
#       ✅ Centralized key management and rotation
#       ✅ Team budgets enforced at the proxy layer, not app layer
#       ✅ Usage metrics automatically captured by proxy
#       ✅ Multiple backend services can share the same proxy
#       ✅ Model fallbacks handled by proxy without app changes
#       ✅ Redis caching at the proxy level (identical prompts served from cache)
#
#     Library approach (calling litellm.completion() directly):
#       ✅ Simpler for single-service apps
#       ❌ No centralized governance
#       ❌ Each service needs all provider keys
#       ❌ No cross-service usage aggregation
#
#   For enterprise with multiple teams and services, the proxy is mandatory.
#
#   The proxy is OpenAI-API-compatible, so we use httpx with the same
#   payload format as OpenAI — LiteLLM handles the translation to
#   each provider's native format.
# ============================================================

import time
import httpx
import asyncio
from typing import AsyncGenerator, List, Optional
from uuid import UUID

from app.config import settings
from app.schemas.chat import ChatMessage, ChatRequest


# -------------------------------------------------------
# HTTP Client — shared across requests (connection pooling)
# -------------------------------------------------------

# A single httpx.AsyncClient is reused across all requests.
# Creating a new client per request is expensive — connection pooling
# reuses TCP connections to the LiteLLM proxy for speed.
_http_client: Optional[httpx.AsyncClient] = None


def get_http_client() -> httpx.AsyncClient:
    """Return the shared async HTTP client, creating it if needed."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            base_url=settings.litellm_proxy_url,
            timeout=httpx.Timeout(
                connect=5.0,    # seconds to establish connection
                read=120.0,     # seconds to wait for response (long for LLM streaming)
                write=10.0,
                pool=5.0,
            ),
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
            ),
        )
    return _http_client


async def close_http_client() -> None:
    """Close the client gracefully at app shutdown."""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()


# -------------------------------------------------------
# Core Chat Completion
# -------------------------------------------------------

async def chat_completion(
    messages: List[ChatMessage],
    model: str,
    virtual_key: str,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    user_id: Optional[str] = None,
) -> dict:
    """
    Send a chat completion request to the LiteLLM proxy (non-streaming).

    Args:
        messages:    List of {role, content} dicts — the conversation history
        model:       Model alias from litellm/config.yaml (e.g. "claude-haiku")
        virtual_key: The LiteLLM virtual key for this user/team (enforces budgets)
        temperature: Sampling temperature (0=deterministic, 1=creative)
        max_tokens:  Maximum tokens in the response
        user_id:     Optional user identifier for LiteLLM's usage tracking

    Returns:
        dict: OpenAI-format response payload with choices[0].message.content
    """
    client = get_http_client()

    payload = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    # Include user_id so LiteLLM can break down spend per user
    if user_id:
        payload["user"] = str(user_id)

    # LiteLLM proxy authenticates via Bearer token —
    # each request uses the user's virtual key so spend is charged to them
    headers = {
        "Authorization": f"Bearer {virtual_key}",
        "Content-Type": "application/json",
    }

    start_time = time.monotonic()

    response = await client.post("/v1/chat/completions", json=payload, headers=headers)
    response.raise_for_status()     # raise httpx.HTTPStatusError for 4xx/5xx

    latency_ms = int((time.monotonic() - start_time) * 1000)

    result = response.json()
    result["_latency_ms"] = latency_ms  # attach for our UsageLog
    return result


async def stream_chat_completion(
    messages: List[ChatMessage],
    model: str,
    virtual_key: str,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> AsyncGenerator[str, None]:
    """
    Stream a chat completion from LiteLLM proxy using Server-Sent Events (SSE).

    ARCHITECT'S NOTE:
      Streaming is essential for good UX — it shows tokens as they arrive
      rather than making the user wait for the full response.
      We use FastAPI's StreamingResponse to pipe SSE chunks to the browser.

      Protocol: LiteLLM returns OpenAI-format SSE:
        data: {"choices": [{"delta": {"content": "token"}}]}
        data: [DONE]

    Yields:
        Individual SSE lines exactly as LiteLLM sends them.
        The FastAPI endpoint passes these straight to the browser.
    """
    client = get_http_client()

    payload = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }

    headers = {
        "Authorization": f"Bearer {virtual_key}",
        "Content-Type": "application/json",
    }

    # Use httpx streaming context — reads the response line by line
    # without buffering the entire response in memory (critical for long outputs)
    async with client.stream("POST", "/v1/chat/completions", json=payload, headers=headers) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if line:    # skip empty keep-alive lines
                yield f"{line}\n\n"     # SSE format requires double newline


# -------------------------------------------------------
# LiteLLM Proxy Admin API — Team & Key Management
# -------------------------------------------------------

async def create_team_in_litellm(team_name: str, team_id: str, budget_usd: float, models: List[str]) -> dict:
    """
    Register a new team in the LiteLLM proxy.

    ARCHITECT'S NOTE:
      LiteLLM's proxy has its own /team/new endpoint. Calling it:
        1. Creates a team entry in LiteLLM's internal Postgres tables
        2. Allows us to issue virtual keys scoped to that team
        3. Enforces the budget_duration and max_budget at proxy level
      We store the returned litellm_team_id in our teams table.
    """
    client = get_http_client()

    payload = {
        "team_alias": team_name,
        "team_id": team_id,                 # pass our UUID as the external team ID
        "max_budget": budget_usd,
        "budget_duration": "30d",           # reset budget every 30 days
        "models": models,                   # restrict to these model aliases
    }

    headers = {"Authorization": f"Bearer {settings.litellm_master_key}"}

    response = await client.post("/team/new", json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


async def create_virtual_key(
    user_id: str,
    team_id: str,
    models: List[str],
    spend_limit_usd: float,
    rpm_limit: int,
) -> str:
    """
    Generate a LiteLLM virtual key for a specific user.

    Returns:
        The virtual key string (e.g. "sk-litellm-...").
        Store this in users.litellm_virtual_key — treat it like a password.
    """
    client = get_http_client()

    payload = {
        "key_alias": f"user-{user_id}",
        "team_id": team_id,
        "models": models,
        "max_budget": spend_limit_usd,
        "rpm_limit": rpm_limit,
        "metadata": {"user_id": user_id},   # extra context visible in LiteLLM logs
    }

    headers = {"Authorization": f"Bearer {settings.litellm_master_key}"}

    response = await client.post("/key/generate", json=payload, headers=headers)
    response.raise_for_status()

    data = response.json()
    return data["key"]  # the actual "sk-litellm-..." string


async def get_team_spend(litellm_team_id: str) -> dict:
    """
    Fetch current spend for a team from the LiteLLM proxy.
    Used to populate the admin dashboard cost tracker.
    """
    client = get_http_client()
    headers = {"Authorization": f"Bearer {settings.litellm_master_key}"}

    response = await client.get(f"/team/info?team_id={litellm_team_id}", headers=headers)
    response.raise_for_status()
    return response.json()


async def list_available_models() -> List[dict]:
    """
    Fetch the list of models registered in the LiteLLM proxy.
    Used to populate the model selector in the UI.
    """
    client = get_http_client()
    headers = {"Authorization": f"Bearer {settings.litellm_master_key}"}

    response = await client.get("/v1/models", headers=headers)
    response.raise_for_status()
    return response.json().get("data", [])
