"""SQLAlchemy declarative base for all REVIVE models."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all REVIVE SQLAlchemy ORM models."""
