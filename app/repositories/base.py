"""Base repository with shared database operations.

Transaction contract:
- Repository methods call ``flush()`` but never ``commit()``.
- The caller (service layer) is responsible for ``commit()``/``rollback()``
  so that multi-entity operations stay atomic (see M-05 / auditoria.md).
"""

from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

T = TypeVar("T")


class BaseRepository(Generic[T]):
    def __init__(self, model: type[T], session: Session):
        self._model = model
        self._session = session

    def get_by_id(self, id: int) -> T | None:
        return self._session.get(self._model, id)

    def get_all(self, skip: int = 0, limit: int = 100) -> list[T]:
        stmt = select(self._model).offset(skip).limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def count(self) -> int:
        """Efficient COUNT(*) executed in the database (O(1) memory)."""
        stmt = select(func.count()).select_from(self._model)
        return self._session.scalar(stmt) or 0

    def add(self, entity: T) -> T:
        self._session.add(entity)
        self._session.flush()
        self._session.refresh(entity)
        return entity

    def delete(self, id: int) -> bool:
        entity = self.get_by_id(id)
        if entity is None:
            return False
        self._session.delete(entity)
        self._session.flush()
        return True