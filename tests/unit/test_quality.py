"""Unit tests for QM — Quality domain repositories."""

from decimal import Decimal

import pytest

from app.domain.quality.inspection import (
    DefectDisposition,
    DefectSeverity,
    InspectionStatus,
    NonConformityCreate,
    QualityInspectionCreate,
    QualityInspectionResult,
)
from app.repositories.quality_repository import (
    NonConformityRepository,
    QualityInspectionRepository,
)


def _create_inspection(session, sample_batch):
    repo = QualityInspectionRepository(session)
    return repo.create(
        QualityInspectionCreate(
            batch_id=sample_batch.id,
            inspection_lot="QI-2026-0001",
        )
    )


class TestQualityInspectionRepository:
    def test_create(self, session, sample_batch):
        inspection = _create_inspection(session, sample_batch)
        assert inspection.id is not None
        assert inspection.inspection_status == "PENDING"
        assert inspection.inspection_lot == "QI-2026-0001"

    def test_get_by_lot(self, session, sample_batch):
        created = _create_inspection(session, sample_batch)
        repo = QualityInspectionRepository(session)
        found = repo.get_by_lot("QI-2026-0001")
        assert found is not None
        assert found.id == created.id

    def test_get_by_lot_not_found(self, session):
        repo = QualityInspectionRepository(session)
        assert repo.get_by_lot("NONEXISTENT") is None

    def test_get_by_batch(self, session, sample_batch):
        created = _create_inspection(session, sample_batch)
        repo = QualityInspectionRepository(session)
        found = repo.get_by_batch(sample_batch.id)
        assert found is not None
        assert found.id == created.id

    def test_update_result_pass(self, session, sample_batch):
        inspection = _create_inspection(session, sample_batch)
        repo = QualityInspectionRepository(session)
        updated = repo.update_result(
            inspection.id,
            InspectionStatus.PASSED,
            pH=Decimal("4.21"),
            alcohol_percent=Decimal("4.7"),
        )
        assert updated is not None
        assert updated.inspection_status == "PASSED"
        assert updated.pH == Decimal("4.21")

    def test_update_result_with_string_status(self, session, sample_batch):
        inspection = _create_inspection(session, sample_batch)
        repo = QualityInspectionRepository(session)
        updated = repo.update_result(inspection.id, "FAILED")
        assert updated is not None
        assert updated.inspection_status == "FAILED"

    def test_update_result_invalid_status_raises(self, session, sample_batch):
        inspection = _create_inspection(session, sample_batch)
        repo = QualityInspectionRepository(session)
        with pytest.raises(ValueError):
            repo.update_result(inspection.id, "INVALID_STATUS")

    def test_update_result_whitelist_protects_identity(self, session, sample_batch):
        inspection = _create_inspection(session, sample_batch)
        original_lot = inspection.inspection_lot
        repo = QualityInspectionRepository(session)
        updated = repo.update_result(
            inspection.id,
            InspectionStatus.IN_PROGRESS,
            inspection_lot="HACKED-LOT",
            batch_id=999999,
        )
        assert updated.inspection_lot == original_lot
        assert updated.batch_id == sample_batch.id

    def test_result_schema_validation(self):
        result = QualityInspectionResult(
            inspection_status=InspectionStatus.PASSED,
            pH=Decimal("4.21"),
            alcohol_percent=Decimal("4.7"),
        )
        assert result.pH == Decimal("4.21")

    def test_result_schema_invalid_ph(self):
        with pytest.raises(Exception):
            QualityInspectionResult(
                inspection_status=InspectionStatus.PASSED,
                pH=Decimal("20"),
            )


class TestNonConformityRepository:
    def test_create_and_get_by_inspection(self, session, sample_batch):
        inspection = _create_inspection(session, sample_batch)
        repo = NonConformityRepository(session)
        nc = repo.create(
            inspection_id=inspection.id,
            data=NonConformityCreate(
                defect_type="OFF_SPEC",
                defect_code="NC-001",
                description="CO2 level below specification",
                severity=DefectSeverity.MAJOR,
                disposition=DefectDisposition.REWORK,
            ),
        )
        assert nc.id is not None
        assert nc.severity == "MAJOR"
        assert nc.disposition == "REWORK"

        found = repo.get_by_inspection(inspection.id)
        assert len(found) == 1
        assert found[0].defect_code == "NC-001"