"""Base repository providing common CRUD patterns for SQLAlchemy models.

All repositories inherit from this base to ensure consistent
session handling and typed interfaces.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from sqlalchemy import select

from src.database.base import Base

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository:
    """Base repository with common CRUD operations.

    Repositories encapsulate persistence logic. They do NOT contain
    business logic, policy decisions, or ML inference.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        """Expose the session for transaction management."""
        return self._session


class CrudRepository[ModelT: Base](BaseRepository):
    """Generic CRUD repository for a single model type.

    Subclasses should set `model_class` to the target SQLAlchemy model.
    """

    model_class: type[ModelT]

    def get_by_id(self, entity_id: uuid.UUID) -> ModelT | None:
        """Retrieve an entity by its primary key."""
        return self._session.get(self.model_class, entity_id)

    def create(self, entity: Base) -> Base:
        """Add a new entity to the session and flush."""
        self._session.add(entity)
        self._session.flush()
        return entity

    def create_all(self, entities: list[Base]) -> list[Base]:
        """Add multiple entities to the session and flush."""
        self._session.add_all(entities)
        self._session.flush()
        return entities

    def delete(self, entity: Base) -> None:
        """Mark an entity for deletion."""
        self._session.delete(entity)
        self._session.flush()

    def list_all(self, *, limit: int = 100, offset: int = 0) -> list[Any]:
        """List entities with pagination."""
        stmt = select(self.model_class).limit(limit).offset(offset)
        result = self._session.execute(stmt)
        return list(result.scalars().all())
