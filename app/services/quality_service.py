"""Quality service — QM business rules.

Owns the transaction boundary: methods commit on success and roll back on
failure, so multi-entity operations stay atomic (M-05). Database exceptions are
translated into domain errors before propagating to the API layer (L-03).
"""

from __future__ import annotations

from logging import getLogger

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateEntityError, EntityNotFoundError
from app.domain.entities import NonConformity, QualityInspection
from app.domain.quality.inspection import (
    InspectionStatus,
    NonConformityCreate,
    QualityInspectionCreate,
    QualityInspectionResult,
)
from app.repositories.production_repository import BatchRepository
from app.repositories.quality_repository import (
    NonConformityRepository,
    QualityInspectionRepository,
)

logger = getLogger(__name__)


class QualityService:
    def __init__(self, session: Session):
        self._session = session
        self.inspections = QualityInspectionRepository(session)
        self.non_conformities = NonConformityRepository(session)
        self.batches = BatchRepository(session)

    # ── Quality Inspections ─────────────────────────────────────────────

    def create_inspection(self, data: QualityInspectionCreate) -> QualityInspection:
        if self.batches.get_by_id(data.batch_id) is None:
            raise EntityNotFoundError("Batch", data.batch_id)

        try:
            inspection = self.inspections.create(data)
            self._session.commit()
            logger.info("Quality inspection %s created", inspection.inspection_lot)
            return inspection
        except IntegrityError:
            self._session.rollback()
            raise DuplicateEntityError("QualityInspection", data.inspection_lot) from None

    def list_inspections(self, skip: int = 0, limit: int = 100) -> list[QualityInspection]:
        return self.inspections.get_all(skip, limit)

    def get_inspection(self, id: int) -> QualityInspection:
        inspection = self.inspections.get_by_id(id)
        if inspection is None:
            raise EntityNotFoundError("QualityInspection", id)
        return inspection

    def get_inspection_by_lot(self, inspection_lot: str) -> QualityInspection:
        inspection = self.inspections.get_by_lot(inspection_lot)
        if inspection is None:
            raise EntityNotFoundError("QualityInspection", inspection_lot)
        return inspection

    def get_inspection_by_batch(self, batch_id: int) -> QualityInspection:
        if self.batches.get_by_id(batch_id) is None:
            raise EntityNotFoundError("Batch", batch_id)
        inspection = self.inspections.get_by_batch(batch_id)
        if inspection is None:
            raise EntityNotFoundError("QualityInspection", batch_id)
        return inspection

    def update_inspection_result(
        self, id: int, data: QualityInspectionResult
    ) -> QualityInspection:
        inspection = self.inspections.get_by_id(id)
        if inspection is None:
            raise EntityNotFoundError("QualityInspection", id)

        result_data = data.model_dump(exclude_unset=True)
        status = result_data.pop("inspection_status")

        updated = self.inspections.update_result(id, status, **result_data)
        self._session.commit()
        logger.info("Quality inspection %s result recorded", updated.inspection_lot)
        return updated

    # ── Non-Conformities ────────────────────────────────────────────────

    def list_non_conformities(self, inspection_id: int) -> list[NonConformity]:
        inspection = self.inspections.get_by_id(inspection_id)
        if inspection is None:
            raise EntityNotFoundError("QualityInspection", inspection_id)
        return self.non_conformities.get_by_inspection(inspection_id)

    def add_non_conformity(
        self, inspection_id: int, data: NonConformityCreate
    ) -> NonConformity:
        inspection = self.inspections.get_by_id(inspection_id)
        if inspection is None:
            raise EntityNotFoundError("QualityInspection", inspection_id)

        nc = self.non_conformities.create(inspection_id, data)
        self._session.commit()
        logger.info(
            "Non-conformity %s recorded on inspection %s",
            nc.defect_code,
            inspection.inspection_lot,
        )
        return nc
