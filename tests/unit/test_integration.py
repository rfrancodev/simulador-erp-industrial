"""Tests for cross-module integration events (TASK-012, TASK-018, TASK-027)."""

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.events import EVENT_BATCH_COMPLETED, EVENT_BATCH_CREATED, event_bus
from app.domain.costing.cost import CostRecordCreate
from app.domain.entities import Batch
from app.domain.production.batch import BatchCreate, BatchStatus
from app.domain.production.recipe import ProductionOrderStatus
from app.domain.quality.inspection import InspectionStatus, QualityInspectionResult
from app.repositories.costing_repository import CostRecordRepository
from app.repositories.quality_repository import QualityInspectionRepository
from app.services.production_service import ProductionService
from app.services.quality_service import QualityService


def _create_batch(service: ProductionService, order_id: int, resource_id: int, number: str):
    return service.create_batch(
        BatchCreate(
            batch_number=number,
            production_order_id=order_id,
            resource_id=resource_id,
            planned_quantity=Decimal("10000"),
        )
    )


class TestBatchCreatedIntegration:
    def test_create_batch_auto_creates_inspection(
        self, session, sample_production_order, sample_resource
    ):
        service = ProductionService(session)
        batch = _create_batch(
            service, sample_production_order.id, sample_resource.id, "B-INT-001"
        )

        inspection = QualityInspectionRepository(session).get_by_batch(batch.id)
        assert inspection is not None
        assert inspection.inspection_status == "PENDING"

    def test_inspection_not_duplicated(self, session, sample_production_order, sample_resource):
        service = ProductionService(session)
        repo = QualityInspectionRepository(session)
        batch = _create_batch(
            service, sample_production_order.id, sample_resource.id, "B-INT-002"
        )
        other = _create_batch(
            service, sample_production_order.id, sample_resource.id, "B-INT-003"
        )
        # Exactly one inspection per batch, no duplicates.
        assert repo.count() == 2
        assert repo.get_by_batch(batch.id) is not None
        assert repo.get_by_batch(other.id) is not None

    def test_create_batch_rolls_back_when_handler_fails(
        self, session, sample_production_order, sample_resource
    ):
        def failing_handler(session, batch):
            raise RuntimeError("handler failed")

        event_bus.subscribe(EVENT_BATCH_CREATED, failing_handler)
        try:
            service = ProductionService(session)
            with pytest.raises(RuntimeError):
                _create_batch(
                    service, sample_production_order.id, sample_resource.id, "B-INT-FAIL"
                )
        finally:
            event_bus.unsubscribe(EVENT_BATCH_CREATED, failing_handler)

        assert session.scalar(select(func.count()).select_from(Batch)) == 0


class TestOrderCompletedIntegration:
    def test_complete_order_auto_creates_cost_record(self, session, sample_production_order):
        service = ProductionService(session)
        service.update_order_status(sample_production_order.id, ProductionOrderStatus.RELEASED)
        service.update_order_status(sample_production_order.id, ProductionOrderStatus.IN_PROCESS)
        service.update_order_status(sample_production_order.id, ProductionOrderStatus.COMPLETED)

        record = CostRecordRepository(session).get_by_order(sample_production_order.id)
        assert record is not None
        assert record.planned_total_cost > 0
        assert record.actual_total_cost is None

    def test_cost_record_not_created_before_completion(self, session, sample_production_order):
        service = ProductionService(session)
        service.update_order_status(sample_production_order.id, ProductionOrderStatus.RELEASED)
        assert CostRecordRepository(session).get_by_order(sample_production_order.id) is None

    def test_cost_record_not_duplicated(self, session, sample_production_order):
        CostRecordRepository(session).create_for_order(
            sample_production_order.id,
            CostRecordCreate(
                production_order_id=sample_production_order.id,
                planned_material_cost=Decimal("100"),
                planned_labor_cost=Decimal("50"),
                planned_machine_cost=Decimal("30"),
                planned_energy_cost=Decimal("20"),
            ),
        )
        session.commit()

        service = ProductionService(session)
        service.update_order_status(sample_production_order.id, ProductionOrderStatus.RELEASED)
        service.update_order_status(sample_production_order.id, ProductionOrderStatus.IN_PROCESS)
        service.update_order_status(sample_production_order.id, ProductionOrderStatus.COMPLETED)

        assert CostRecordRepository(session).count() == 1


class TestReworkIntegration:
    def test_inspection_failed_applies_rework_to_existing_cost_record(
        self, session, sample_production_order, sample_resource
    ):
        service = ProductionService(session)
        service.update_order_status(sample_production_order.id, ProductionOrderStatus.RELEASED)
        service.update_order_status(sample_production_order.id, ProductionOrderStatus.IN_PROCESS)
        service.update_order_status(sample_production_order.id, ProductionOrderStatus.COMPLETED)

        record = CostRecordRepository(session).get_by_order(sample_production_order.id)
        assert record.actual_total_cost is None

        batch = _create_batch(service, sample_production_order.id, sample_resource.id, "B-REWORK")
        inspection = QualityInspectionRepository(session).get_by_batch(batch.id)

        service.update_batch_status(batch.id, BatchStatus.IN_PRODUCTION)
        service.update_batch_status(batch.id, BatchStatus.COMPLETED)

        qsvc = QualityService(session)
        qsvc.update_inspection_result(
            inspection.id, QualityInspectionResult(inspection_status=InspectionStatus.IN_PROGRESS)
        )
        qsvc.update_inspection_result(
            inspection.id, QualityInspectionResult(inspection_status=InspectionStatus.FAILED)
        )

        session.refresh(record)
        assert record.actual_total_cost is not None
        assert record.actual_total_cost > record.planned_total_cost

    def test_order_completed_with_failed_inspection_applies_rework(
        self, session, sample_production_order, sample_resource
    ):
        service = ProductionService(session)
        batch = _create_batch(service, sample_production_order.id, sample_resource.id, "B-REWORK2")
        inspection = QualityInspectionRepository(session).get_by_batch(batch.id)

        service.update_batch_status(batch.id, BatchStatus.IN_PRODUCTION)
        service.update_batch_status(batch.id, BatchStatus.COMPLETED)

        qsvc = QualityService(session)
        qsvc.update_inspection_result(
            inspection.id, QualityInspectionResult(inspection_status=InspectionStatus.IN_PROGRESS)
        )
        qsvc.update_inspection_result(
            inspection.id, QualityInspectionResult(inspection_status=InspectionStatus.FAILED)
        )

        service.update_order_status(sample_production_order.id, ProductionOrderStatus.RELEASED)
        service.update_order_status(sample_production_order.id, ProductionOrderStatus.IN_PROCESS)
        service.update_order_status(sample_production_order.id, ProductionOrderStatus.COMPLETED)

        record = CostRecordRepository(session).get_by_order(sample_production_order.id)
        assert record.actual_total_cost is not None
        assert record.actual_total_cost > record.planned_total_cost


def _release_order(service: ProductionService, order_id: int) -> None:
    service.update_order_status(order_id, ProductionOrderStatus.RELEASED)
    service.update_order_status(order_id, ProductionOrderStatus.IN_PROCESS)


class TestBatchCompletedIntegration:
    def test_last_batch_completed_completes_order_and_creates_cost_record(
        self, session, sample_production_order, sample_resource
    ):
        service = ProductionService(session)
        _release_order(service, sample_production_order.id)
        batch = _create_batch(
            service, sample_production_order.id, sample_resource.id, "B-AUTO-001"
        )

        service.update_batch_status(batch.id, BatchStatus.IN_PRODUCTION)
        service.update_batch_status(batch.id, BatchStatus.COMPLETED)

        session.refresh(sample_production_order)
        assert sample_production_order.status == "COMPLETED"
        assert sample_production_order.actual_start is not None
        assert sample_production_order.actual_end is not None
        record = CostRecordRepository(session).get_by_order(sample_production_order.id)
        assert record is not None
        assert record.planned_total_cost > 0

    def test_two_batches_order_completes_only_with_last(
        self, session, sample_production_order, sample_resource
    ):
        service = ProductionService(session)
        _release_order(service, sample_production_order.id)
        b1 = _create_batch(
            service, sample_production_order.id, sample_resource.id, "B-AUTO-002"
        )
        b2 = _create_batch(
            service, sample_production_order.id, sample_resource.id, "B-AUTO-003"
        )

        service.update_batch_status(b1.id, BatchStatus.IN_PRODUCTION)
        service.update_batch_status(b1.id, BatchStatus.COMPLETED)

        session.refresh(sample_production_order)
        assert sample_production_order.status == "IN_PROCESS"
        assert CostRecordRepository(session).get_by_order(sample_production_order.id) is None

        service.update_batch_status(b2.id, BatchStatus.IN_PRODUCTION)
        service.update_batch_status(b2.id, BatchStatus.COMPLETED)

        session.refresh(sample_production_order)
        assert sample_production_order.status == "COMPLETED"
        assert CostRecordRepository(session).get_by_order(sample_production_order.id) is not None

    def test_last_batch_scrap_completes_order(
        self, session, sample_production_order, sample_resource
    ):
        service = ProductionService(session)
        _release_order(service, sample_production_order.id)
        batch = _create_batch(
            service, sample_production_order.id, sample_resource.id, "B-AUTO-SCRAP"
        )

        service.update_batch_status(batch.id, BatchStatus.IN_PRODUCTION)
        service.update_batch_status(batch.id, BatchStatus.SCRAP)

        session.refresh(sample_production_order)
        assert sample_production_order.status == "COMPLETED"
        assert CostRecordRepository(session).get_by_order(sample_production_order.id) is not None

    def test_batch_completed_does_not_complete_created_order(
        self, session, sample_production_order, sample_resource
    ):
        service = ProductionService(session)
        batch = _create_batch(
            service, sample_production_order.id, sample_resource.id, "B-AUTO-CREATED"
        )

        service.update_batch_status(batch.id, BatchStatus.IN_PRODUCTION)
        service.update_batch_status(batch.id, BatchStatus.COMPLETED)

        session.refresh(sample_production_order)
        assert sample_production_order.status == "CREATED"
        assert CostRecordRepository(session).get_by_order(sample_production_order.id) is None

    def test_pending_rework_batch_blocks_order_completion(
        self, session, sample_production_order, sample_resource
    ):
        service = ProductionService(session)
        _release_order(service, sample_production_order.id)
        b1 = _create_batch(
            service, sample_production_order.id, sample_resource.id, "B-AUTO-REW-1"
        )
        b2 = _create_batch(
            service, sample_production_order.id, sample_resource.id, "B-AUTO-REW-2"
        )

        service.update_batch_status(b1.id, BatchStatus.IN_PRODUCTION)
        service.update_batch_status(b1.id, BatchStatus.COMPLETED)
        service.update_batch_status(b2.id, BatchStatus.IN_PRODUCTION)
        service.update_batch_status(b2.id, BatchStatus.REWORK)

        session.refresh(sample_production_order)
        assert sample_production_order.status == "IN_PROCESS"
        assert CostRecordRepository(session).get_by_order(sample_production_order.id) is None

        service.update_batch_status(b2.id, BatchStatus.IN_PRODUCTION)
        service.update_batch_status(b2.id, BatchStatus.COMPLETED)

        session.refresh(sample_production_order)
        assert sample_production_order.status == "COMPLETED"
        assert CostRecordRepository(session).get_by_order(sample_production_order.id) is not None

    def test_handler_failure_rolls_back_batch_order_and_cost_record(
        self, session, sample_production_order, sample_resource
    ):
        def failing_handler(session, batch):
            raise RuntimeError("batch completed handler failed")

        event_bus.subscribe(EVENT_BATCH_COMPLETED, failing_handler)
        try:
            service = ProductionService(session)
            _release_order(service, sample_production_order.id)
            batch = _create_batch(
                service, sample_production_order.id, sample_resource.id, "B-AUTO-FAIL"
            )
            service.update_batch_status(batch.id, BatchStatus.IN_PRODUCTION)
            with pytest.raises(RuntimeError):
                service.update_batch_status(batch.id, BatchStatus.COMPLETED)
        finally:
            event_bus.unsubscribe(EVENT_BATCH_COMPLETED, failing_handler)

        session.refresh(batch)
        assert batch.status == "IN_PRODUCTION"
        session.refresh(sample_production_order)
        assert sample_production_order.status == "IN_PROCESS"
        assert CostRecordRepository(session).get_by_order(sample_production_order.id) is None

    def test_repeated_event_processing_is_idempotent(
        self, session, sample_production_order, sample_resource
    ):
        service = ProductionService(session)
        _release_order(service, sample_production_order.id)
        batch = _create_batch(
            service, sample_production_order.id, sample_resource.id, "B-AUTO-IDEM"
        )
        service.update_batch_status(batch.id, BatchStatus.IN_PRODUCTION)
        service.update_batch_status(batch.id, BatchStatus.COMPLETED)

        session.refresh(sample_production_order)
        assert sample_production_order.status == "COMPLETED"
        actual_end = sample_production_order.actual_end
        assert actual_end is not None
        assert CostRecordRepository(session).count() == 1

        event_bus.publish(EVENT_BATCH_COMPLETED, session=session, batch=batch)
        session.refresh(sample_production_order)
        assert sample_production_order.status == "COMPLETED"
        assert sample_production_order.actual_end == actual_end
        assert CostRecordRepository(session).count() == 1
