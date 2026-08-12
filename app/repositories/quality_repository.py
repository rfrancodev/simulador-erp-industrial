"""Repository for QM — Quality Management domain."""

from logging import getLogger

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.domain.entities import NonConformity, QualityInspection
from app.domain.quality.inspection import (
    InspectionStatus,
    NonConformityCreate,
    QualityInspectionCreate,
)
from app.repositories.base import BaseRepository

logger = getLogger(__name__)

# Whitelist of mutable inspection fields (M-02). Immutable identity fields
# (id, batch_id, inspection_lot, inspection_date) can never be overwritten.
_MUTABLE_INSPECTION_FIELDS = frozenset(
    {
        "pH",
        "alcohol_percent",
        "temperature",
        "co2_level",
        "appearance",
        "microbiological_status",
        "inspector_notes",
        "result_date",
    }
)


class QualityInspectionRepository(BaseRepository[QualityInspection]):
    def __init__(self, session: Session):
        super().__init__(QualityInspection, session)

    def get_by_lot(self, inspection_lot: str) -> QualityInspection | None:
        stmt = select(QualityInspection).where(QualityInspection.inspection_lot == inspection_lot)
        return self._session.execute(stmt).scalar_one_or_none()

    def get_by_batch(self, batch_id: int) -> QualityInspection | None:
        stmt = (
            select(QualityInspection)
            .options(joinedload(QualityInspection.non_conformities))
            .where(QualityInspection.batch_id == batch_id)
        )
        return self._session.execute(stmt).unique().scalar_one_or_none()

    def create(self, data: QualityInspectionCreate) -> QualityInspection:
        inspection = QualityInspection(
            batch_id=data.batch_id,
            inspection_lot=data.inspection_lot,
            inspection_status=InspectionStatus.PENDING.value,
        )
        return self.add(inspection)

    def update_result(
        self, id: int, status: str | InspectionStatus, **params
    ) -> QualityInspection | None:
        inspection = self.get_by_id(id)
        if inspection is None:
            return None

        # Validate the status against the domain enum before persisting.
        status_value = status.value if isinstance(status, InspectionStatus) else InspectionStatus(status).value
        inspection.inspection_status = status_value

        for key, value in params.items():
            if key in _MUTABLE_INSPECTION_FIELDS and value is not None:
                setattr(inspection, key, value)
        self._session.flush()
        self._session.refresh(inspection)
        logger.info("Quality inspection %s status updated to %s", inspection.inspection_lot, status_value)
        return inspection


class NonConformityRepository(BaseRepository[NonConformity]):
    def __init__(self, session: Session):
        super().__init__(NonConformity, session)

    def get_by_inspection(self, inspection_id: int, skip: int = 0, limit: int = 100) -> list[NonConformity]:
        stmt = (
            select(NonConformity)
            .where(NonConformity.inspection_id == inspection_id)
            .offset(skip)
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars().all())

    def count_by_inspection(self, inspection_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(NonConformity)
            .where(NonConformity.inspection_id == inspection_id)
        )
        return self._session.scalar(stmt) or 0

    def create(self, inspection_id: int, data: NonConformityCreate) -> NonConformity:
        nc = NonConformity(
            inspection_id=inspection_id,
            defect_type=data.defect_type,
            defect_code=data.defect_code,
            description=data.description,
            severity=data.severity.value,
            disposition=data.disposition.value,
        )
        return self.add(nc)
