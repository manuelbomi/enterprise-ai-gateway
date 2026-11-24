# ============================================================
# main.py — FastAPI Application Entry Point
#
# ARCHITECT'S NOTE:
#   This file bootstraps the entire backend.
#   It wires together:
#     - FastAPI app instance with metadata for auto-generated Swagger docs
#     - CORS middleware (allows the React frontend to call the API)
#     - All API routers (auth, chat, admin)
#     - Startup/shutdown lifecycle hooks (DB connection warmup, HTTP client)
#
#   Run locally:
#     uvicorn main:app --reload --port 8000
#
#   Swagger UI: http://localhost:8000/docs
#   ReDoc:      http://localhost:8000/redoc
# ============================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.admin import router as admin_router
from app.services.litellm_service import close_http_client


# -------------------------------------------------------
# Lifespan context manager
# Replaces deprecated @app.on_event("startup") / "shutdown"
# -------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Code before 'yield' runs at startup.
    Code after 'yield' runs at shutdown.
    Use this for DB connection warmup, background task init, etc.
    """
    # Startup
    print(f"[STARTUP] {settings.app_name} starting in {settings.environment} mode")
    # In production: run Alembic migrations here programmatically if desired
    # For now, migrations are run manually: alembic upgrade head

    yield  # App is running and serving requests here

    # Shutdown — clean up resources
    await close_http_client()
    print("[SHUTDOWN] HTTP client closed. Goodbye.")


# -------------------------------------------------------
# FastAPI Application
# -------------------------------------------------------

app = FastAPI(
    title=settings.app_name,
    description="""
## Enterprise AI Gateway API

A production-ready multi-provider AI platform built on LiteLLM.

### Key Features
- **Multi-provider routing** — OpenAI, Anthropic, Google, Mistral via unified API
- **Team-based governance** — model access and budgets controlled per department
- **Streaming support** — real-time token output via Server-Sent Events
- **Cost tracking** — per-user, per-team, per-model spend analytics
- **Role-based access** — super_admin, team_admin, member hierarchy

### Authentication
All endpoints (except /auth/login) require a Bearer JWT token.
Obtain one via POST /auth/login.
    """,
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,   # disable Swagger in production
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)


# -------------------------------------------------------
# CORS Middleware
# ARCHITECT'S NOTE:
#   CORS allows the browser-based React app (running on a different
#   port/domain) to call this API. In production, only your actual
#   frontend domain should be in ALLOWED_ORIGINS.
#   NEVER use allow_origins=["*"] in production — it allows any website
#   to make authenticated requests using the user's cookies/tokens.
# -------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,     # allow cookies and auth headers
    allow_methods=["*"],        # GET, POST, PUT, DELETE, OPTIONS
    allow_headers=["*"],        # Authorization, Content-Type, etc.
)


# -------------------------------------------------------
# API Routers — register all endpoint groups
# -------------------------------------------------------

app.include_router(auth_router)     # /auth/login, /auth/register, /auth/me
app.include_router(chat_router)     # /chat/completions, /chat/sessions
app.include_router(admin_router)    # /admin/teams, /admin/analytics


# -------------------------------------------------------
# Health Check — used by Docker healthcheck and load balancers
# -------------------------------------------------------

@app.get("/health", tags=["System"])
async def health_check():
    """
    Returns 200 OK when the app is running.
    Load balancers and Kubernetes probes call this endpoint
    to decide whether to route traffic to this instance.
    """
    return {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.environment,
        "version": "1.0.0",
    }


@app.get("/", tags=["System"])
async def root():
    return {
        "message": f"Welcome to {settings.app_name}",
        "docs": "/docs" if settings.debug else "Swagger disabled in production",
    }
