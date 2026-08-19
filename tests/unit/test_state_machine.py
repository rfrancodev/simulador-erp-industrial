"""Tests for domain state machines (M-14, M-15)."""

import pytest

from app.core.exceptions import (
    BatchNotCompletedError,
    EntityNotFoundError,
    InvalidStateTransitionError,
)
from app.domain.production.batch import BatchStatus
from app.domain.production.recipe import ProductionOrderStatus
from app.domain.quality.inspection import (
    InspectionStatus,
    QualityInspectionCreate,
    QualityInspectionResult,
)
from app.domain.state_machine import (
    BATCH_TRANSITIONS,
    INSPECTION_TRANSITIONS,
    PRODUCTION_ORDER_TRANSITIONS,
    validate_transition,
)
from app.services.production_service import ProductionService
from app.services.quality_service import QualityService


class TestValidateTransition:
    def test_valid_transition_passes(self):
        validate_transition(
            PRODUCTION_ORDER_TRANSITIONS,
            ProductionOrderStatus.CREATED,
            ProductionOrderStatus.RELEASED,
            entity="ProductionOrder",
        )

    def test_invalid_transition_raises(self):
        with pytest.raises(InvalidStateTransitionError) as exc:
            validate_transition(
                PRODUCTION_ORDER_TRANSITIONS,
                ProductionOrderStatus.CREATED,
                ProductionOrderStatus.COMPLETED,
                entity="ProductionOrder",
            )
        assert "CREATED -> COMPLETED" in str(exc.value)

    def test_terminal_state_has_no_transitions(self):
        with pytest.raises(InvalidStateTransitionError):
            validate_transition(
                PRODUCTION_ORDER_TRANSITIONS,
                ProductionOrderStatus.DELIVERED,
                ProductionOrderStatus.CLOSED,
                entity="ProductionOrder",
            )


class TestProductionOrderStateMachine:
    def test_full_lifecycle(self, session, sample_production_order):
        svc = ProductionService(session)
        order = svc.update_order_status(sample_production_order.id, ProductionOrderStatus.RELEASED)
        assert order.status == "RELEASED"
        order = svc.update_order_status(order.id, ProductionOrderStatus.IN_PROCESS)
        assert order.status == "IN_PROCESS"
        assert order.actual_start is not None
        order = svc.update_order_status(order.id, ProductionOrderStatus.COMPLETED)
        assert order.status == "COMPLETED"
        assert order.actual_end is not None

    def test_skipping_states_rejected(self, session, sample_production_order):
        svc = ProductionService(session)
        with pytest.raises(InvalidStateTransitionError):
            svc.update_order_status(sample_production_order.id, ProductionOrderStatus.IN_PROCESS)


class TestBatchStateMachine:
    def test_created_to_in_production(self, session, sample_batch):
        svc = ProductionService(session)
        updated = svc.update_batch_status(sample_batch.id, BatchStatus.IN_PRODUCTION)
        assert updated.status == "IN_PRODUCTION"

    def test_in_production_to_completed(self, session, sample_batch):
        svc = ProductionService(session)
        svc.update_batch_status(sample_batch.id, BatchStatus.IN_PRODUCTION)
        updated = svc.update_batch_status(sample_batch.id, BatchStatus.COMPLETED)
        assert updated.status == "COMPLETED"
        assert updated.completed_at is not None

    def test_in_production_to_rework(self, session, sample_batch):
        svc = ProductionService(session)
        svc.update_batch_status(sample_batch.id, BatchStatus.IN_PRODUCTION)
        updated = svc.update_batch_status(sample_batch.id, BatchStatus.REWORK)
        assert updated.status == "REWORK"

    def test_in_production_to_scrap(self, session, sample_batch):
        svc = ProductionService(session)
        svc.update_batch_status(sample_batch.id, BatchStatus.IN_PRODUCTION)
        updated = svc.update_batch_status(sample_batch.id, BatchStatus.SCRAP)
        assert updated.status == "SCRAP"

    def test_rework_to_in_production(self, session, sample_batch):
        svc = ProductionService(session)
        svc.update_batch_status(sample_batch.id, BatchStatus.IN_PRODUCTION)
        svc.update_batch_status(sample_batch.id, BatchStatus.REWORK)
        updated = svc.update_batch_status(sample_batch.id, BatchStatus.IN_PRODUCTION)
        assert updated.status == "IN_PRODUCTION"
        assert updated.completed_at is None

    def test_skipping_in_production_rejected(self, session, sample_batch):
        svc = ProductionService(session)
        with pytest.raises(InvalidStateTransitionError):
            svc.update_batch_status(sample_batch.id, BatchStatus.COMPLETED)

    def test_completed_is_terminal(self, session, sample_batch):
        svc = ProductionService(session)
        svc.update_batch_status(sample_batch.id, BatchStatus.IN_PRODUCTION)
        svc.update_batch_status(sample_batch.id, BatchStatus.COMPLETED)
        with pytest.raises(InvalidStateTransitionError):
            svc.update_batch_status(sample_batch.id, BatchStatus.IN_PRODUCTION)

    def test_scrap_is_terminal(self, session, sample_batch):
        svc = ProductionService(session)
        svc.update_batch_status(sample_batch.id, BatchStatus.IN_PRODUCTION)
        svc.update_batch_status(sample_batch.id, BatchStatus.SCRAP)
        with pytest.raises(InvalidStateTransitionError):
            svc.update_batch_status(sample_batch.id, BatchStatus.IN_PRODUCTION)

    def test_batch_not_found(self, session):
        svc = ProductionService(session)
        with pytest.raises(EntityNotFoundError):
            svc.update_batch_status(9999, BatchStatus.IN_PRODUCTION)

    def test_backwards_transition_rejected(self, session, sample_production_order):
        svc = ProductionService(session)
        svc.update_order_status(sample_production_order.id, ProductionOrderStatus.RELEASED)
        with pytest.raises(InvalidStateTransitionError):
            svc.update_order_status(sample_production_order.id, ProductionOrderStatus.CREATED)

    def test_partial_can_be_completed(self, session, sample_production_order):
        svc = ProductionService(session)
        svc.update_order_status(sample_production_order.id, ProductionOrderStatus.RELEASED)
        svc.update_order_status(sample_production_order.id, ProductionOrderStatus.IN_PROCESS)
        order = svc.update_order_status(sample_production_order.id, ProductionOrderStatus.PARTIAL)
        assert order.status == "PARTIAL"
        order = svc.update_order_status(sample_production_order.id, ProductionOrderStatus.COMPLETED)
        assert order.status == "COMPLETED"

    def test_order_not_found(self, session):
        svc = ProductionService(session)
        with pytest.raises(EntityNotFoundError):
            svc.update_order_status(9999, ProductionOrderStatus.RELEASED)


class TestInspectionStateMachine:
    def _create_inspection(self, session, sample_batch, lot="QI-STATE"):
        svc = QualityService(session)
        return svc.create_inspection(QualityInspectionCreate(batch_id=sample_batch.id, inspection_lot=lot))

    def _complete_batch(self, session, sample_batch) -> None:
        svc = ProductionService(session)
        svc.update_batch_status(sample_batch.id, BatchStatus.IN_PRODUCTION)
        svc.update_batch_status(sample_batch.id, BatchStatus.COMPLETED)

    def test_pending_to_passed_rejected(self, session, sample_batch):
        svc = QualityService(session)
        inspection = self._create_inspection(session, sample_batch)
        with pytest.raises(InvalidStateTransitionError):
            svc.update_inspection_result(
                inspection.id,
                QualityInspectionResult(inspection_status=InspectionStatus.PASSED),
            )

    def test_full_lifecycle(self, session, sample_batch):
        svc = QualityService(session)
        inspection = self._create_inspection(session, sample_batch)
        svc.update_inspection_result(
            inspection.id,
            QualityInspectionResult(inspection_status=InspectionStatus.IN_PROGRESS),
        )
        self._complete_batch(session, sample_batch)
        updated = svc.update_inspection_result(
            inspection.id,
            QualityInspectionResult(
                inspection_status=InspectionStatus.PASSED,
                pH="4.20",
                alcohol_percent="4.7",
            ),
        )
        assert updated.inspection_status == "PASSED"
        assert updated.result_date is not None

    def test_final_result_rejected_when_batch_not_completed(self, session, sample_batch):
        svc = QualityService(session)
        inspection = self._create_inspection(session, sample_batch)
        svc.update_inspection_result(
            inspection.id,
            QualityInspectionResult(inspection_status=InspectionStatus.IN_PROGRESS),
        )
        with pytest.raises(BatchNotCompletedError):
            svc.update_inspection_result(
                inspection.id,
                QualityInspectionResult(inspection_status=InspectionStatus.PASSED),
            )

    def test_failed_to_passed_rejected(self, session, sample_batch):
        svc = QualityService(session)
        inspection = self._create_inspection(session, sample_batch)
        svc.update_inspection_result(
            inspection.id,
            QualityInspectionResult(inspection_status=InspectionStatus.IN_PROGRESS),
        )
        self._complete_batch(session, sample_batch)
        svc.update_inspection_result(
            inspection.id,
            QualityInspectionResult(inspection_status=InspectionStatus.FAILED),
        )
        with pytest.raises(InvalidStateTransitionError):
            svc.update_inspection_result(
                inspection.id,
                QualityInspectionResult(inspection_status=InspectionStatus.PASSED),
            )

    def test_failed_can_rework_then_inspect_again(self, session, sample_batch):
        svc = QualityService(session)
        inspection = self._create_inspection(session, sample_batch)
        svc.update_inspection_result(
            inspection.id,
            QualityInspectionResult(inspection_status=InspectionStatus.IN_PROGRESS),
        )
        self._complete_batch(session, sample_batch)
        svc.update_inspection_result(
            inspection.id,
            QualityInspectionResult(inspection_status=InspectionStatus.FAILED),
        )
        svc.update_inspection_result(
            inspection.id,
            QualityInspectionResult(inspection_status=InspectionStatus.REWORK),
        )
        updated = svc.update_inspection_result(
            inspection.id,
            QualityInspectionResult(inspection_status=InspectionStatus.IN_PROGRESS),
        )
        assert updated.inspection_status == "IN_PROGRESS"
