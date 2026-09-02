"""Database connection and session management.

Provides SQLAlchemy engine and session factories for both
sync (Alembic) and async (application) usage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from src.api.config import settings

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.ext.asyncio import AsyncEngine


def get_sync_engine(database_url: str | None = None, echo: bool = False) -> Engine:
    """Create a synchronous SQLAlchemy engine (used by Alembic and tests).

    Args:
        database_url: Database connection string. Falls back to settings.
        echo: Whether to echo SQL statements.
    """
    url = database_url or settings.database_url
    # Convert async URL to sync if needed
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    elif url.startswith("sqlite+aiosqlite://"):
        url = url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return create_engine(url, echo=echo)


def get_async_engine(database_url: str | None = None, echo: bool = False) -> AsyncEngine:
    """Create an async SQLAlchemy engine for the application.

    Args:
        database_url: Database connection string. Falls back to settings.
        echo: Whether to echo SQL statements.
    """
    url = database_url or settings.database_url
    return create_async_engine(url, echo=echo)


def get_sync_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    """Create a sync session factory bound to the given engine."""
    eng = engine or get_sync_engine()
    return sessionmaker(bind=eng, expire_on_commit=False)


def get_async_session_factory(
    engine: AsyncEngine | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the given engine."""
    eng = engine or get_async_engine()
    return async_sessionmaker(bind=eng, expire_on_commit=False, class_=AsyncSession)
