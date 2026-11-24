# ============================================================
# app/database.py — Database Connection & Session Management
#
# ARCHITECT'S NOTE:
#   SQLAlchemy 2.0 introduced a new "2.0 style" API that is
#   async-friendly and uses type annotations throughout.
#   We use the async engine with asyncpg for best performance.
#
#   Pattern used here: "dependency injection via FastAPI Depends"
#   Every API endpoint that needs the DB receives a session object
#   injected by FastAPI — it is automatically closed after the
#   request completes, preventing connection leaks.
#
#   Alembic handles migrations. Never use create_all() in production.
# ============================================================

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator

from app.config import settings


# -------------------------------------------------------
# 1. DATABASE ENGINE
#    asyncpg driver gives us non-blocking DB calls, which
#    is critical — blocking the event loop in an async
#    FastAPI app would serialize all requests.
# -------------------------------------------------------
engine: AsyncEngine = create_async_engine(
    # Replace postgresql:// with postgresql+asyncpg:// for async driver
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.debug,    # log all SQL in debug mode (disable in production)
    pool_size=10,           # maintain up to 10 persistent connections
    max_overflow=20,        # allow up to 20 extra connections under load
    pool_pre_ping=True,     # test connection health before using from pool
)


# -------------------------------------------------------
# 2. SESSION FACTORY
#    async_sessionmaker is the async equivalent of sessionmaker.
#    expire_on_commit=False keeps loaded objects usable after commit —
#    important for returning data from endpoints after a write.
# -------------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# -------------------------------------------------------
# 3. BASE CLASS
#    All ORM models inherit from this. SQLAlchemy uses it to
#    discover tables and generate migrations via Alembic.
# -------------------------------------------------------
class Base(DeclarativeBase):
    pass


# -------------------------------------------------------
# 4. DEPENDENCY INJECTION HELPER
#    FastAPI injects this into route handlers via Depends(get_db).
#    The 'yield' makes it a context manager — session is automatically
#    closed (and rolled back on error) after the request finishes.
# -------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a DB session per request.

    Usage in a route:
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()      # commit if no exception was raised
        except Exception:
            await session.rollback()    # roll back on any error
            raise
        # session.close() is called automatically by the context manager
