"""Tests for TASK-028 — Batch/Order actual quantity consolidation (PP-PI).

When a Batch transitions to ``COMPLETED`` via the API, its ``actual_quantity``
and ``yield_percent`` are consolidated from the final Production Confirmation
(``is_final=True``, newest ``confirmation_time``, highest ``id`` on tie).
Completing a Production Order (auto TASK-027 or manual) sums the available
batch actuals into ``order.actual_quantity``.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.events import EVENT_BATCH_COMPLETED, event_bus
from app.domain.production.batch import BatchCreate, BatchStatus, ProductionConfirmationCreate
from app.domain.production.recipe import ProductionOrderStatus
from app.services.production_service import ProductionService


def _create_batch(
    service: ProductionService,
    order_id: int,
    resource_id: int,
    number: str,
    planned: Decimal = Decimal("10000"),
):
    return service.create_batch(
        BatchCreate(
            batch_number=number,
            production_order_id=order_id,
            resource_id=resource_id,
            planned_quantity=planned,
        )
    )


def _confirm(
    service: ProductionService,
    batch_id: int,
    quantity: Decimal,
    operation: str = "Filling",
    is_final: bool = True,
    when: datetime | None = None,
):
    return service.create_confirmation(
        ProductionConfirmationCreate(
            batch_id=batch_id,
            operation=operation,
            quantity=quantity,
            unit="L",
            confirmation_time=when or datetime.now(UTC),
            is_final=is_final,
        )
    )


def _complete_batch(service: ProductionService, batch_id: int) -> None:
    service.update_batch_status(batch_id, BatchStatus.IN_PRODUCTION)
    service.update_batch_status(batch_id, BatchStatus.COMPLETED)


class TestBatchConsolidation:
    def test_single_final_confirmation_sets_batch_actuals(
        self, session, sample_production_order, sample_resource
    ):
        service = ProductionService(session)
        batch = _create_batch(service, sample_production_order.id, sample_resource.id, "B-ACT-001")
        _confirm(service, batch.id, Decimal("9500"))
        _complete_batch(service, batch.id)

        session.refresh(batch)
        assert batch.actual_quantity == Decimal("9500.000")
        assert batch.yield_percent == Decimal("95.00")

    def test_only_latest_final_confirmation_is_used(
        self, session, sample_production_order, sample_resource
    ):
        service = ProductionService(session)
        batch = _create_batch(service, sample_production_order.id, sample_resource.id, "B-ACT-002")
        base = datetime.now(UTC)
        _confirm(service, batch.id, Decimal("9000"), operation="Mashing", is_final=False, when=base)
        _confirm(
            service,
            batch.id,
            Decimal("9700"),
            operation="Filling",
            is_final=True,
            when=base + timedelta(minutes=10),
        )
        _confirm(service, batch.id, Decimal("5000"), operation="Draining", is_final=False, when=base + timedelta(minutes=20))
        _complete_batch(service, batch.id)

        session.refresh(batch)
        assert batch.actual_quantity == Decimal("9700.000")

    def test_latest_confirmation_time_wins_among_finals(
        self, session, sample_production_order, sample_resource
    ):
        service = ProductionService(session)
        batch = _create_batch(service, sample_production_order.id, sample_resource.id, "B-ACT-003")
        base = datetime.now(UTC)
        _confirm(service, batch.id, Decimal("9600"), when=base)
        _confirm(service, batch.id, Decimal("9800"), when=base + timedelta(minutes=5))
        _complete_batch(service, batch.id)

        session.refresh(batch)
        assert batch.actual_quantity == Decimal("9800.000")

    def test_tie_on_confirmation_time_prefers_higher_id(
        self, session, sample_production_order, sample_resource
    ):
        service = ProductionService(session)
        batch = _create_batch(service, sample_production_order.id, sample_resource.id, "B-ACT-004")
        when = datetime.now(UTC)
        _confirm(service, batch.id, Decimal("9600"), when=when)
        _confirm(service, batch.id, Decimal("9900"), when=when)
        _complete_batch(service, batch.id)

        session.refresh(batch)
        assert batch.actual_quantity == Decimal("9900.000")

    def test_no_final_confirmation_keeps_actuals_none(
        self, session, sample_production_order, sample_resource
    ):
        service = ProductionService(session)
        batch = _create_batch(service, sample_production_order.id, sample_resource.id, "B-ACT-005")
        _confirm(service, batch.id, Decimal("9500"), is_final=False)
        _complete_batch(service, batch.id)

        session.refresh(batch)
        assert batch.actual_quantity is None
        assert batch.yield_percent is None

    def test_non_completed_transitions_do_not_consolidate(
        self, session, sample_production_order, sample_resource
    ):
        service = ProductionService(session)
        batch = _create_batch(service, sample_production_order.id, sample_resource.id, "B-ACT-006")
        _confirm(service, batch.id, Decimal("9500"))
        service.update_batch_status(batch.id, BatchStatus.IN_PRODUCTION)
        service.update_batch_status(batch.id, BatchStatus.REWORK)
        service.update_batch_status(batch.id, BatchStatus.IN_PRODUCTION)
        service.update_batch_status(batch.id, BatchStatus.SCRAP)

        session.refresh(batch)
        assert batch.actual_quantity is None
        assert batch.yield_percent is None

    def test_decimal_precision(self, session, sample_production_order, sample_resource):
        service = ProductionService(session)
        batch = _create_batch(service, sample_production_order.id, sample_resource.id, "B-ACT-PREC")
        _confirm(service, batch.id, Decimal("3333.333"))
        _complete_batch(service, batch.id)

        session.refresh(batch)
        assert batch.actual_quantity == Decimal("3333.333")
        assert batch.yield_percent == Decimal("33.33")


class TestOrderConsolidation:
    def test_last_batch_completed_sums_order_actual_quantity(
        self, session, sample_production_order, sample_resource
    ):
        service = ProductionService(session)
        service.update_order_status(sample_production_order.id, ProductionOrderStatus.RELEASED)
        service.update_order_status(sample_production_order.id, ProductionOrderStatus.IN_PROCESS)
        b1 = _create_batch(service, sample_production_order.id, sample_resource.id, "B-ACT-007")
        b2 = _create_batch(service, sample_production_order.id, sample_resource.id, "B-ACT-008")
        _confirm(service, b1.id, Decimal("9500"))
        _complete_batch(service, b1.id)

        session.refresh(sample_production_order)
        assert sample_production_order.status == "IN_PROCESS"
        assert sample_production_order.actual_quantity is None

        _confirm(service, b2.id, Decimal("9800"))
        _complete_batch(service, b2.id)

        session.refresh(sample_production_order)
        assert sample_production_order.status == "COMPLETED"
        assert sample_production_order.actual_quantity == Decimal("19300.000")

    def test_manual_order_completion_sets_actual_quantity(
        self, session, sample_production_order, sample_resource
    ):
        service = ProductionService(session)
        batch = _create_batch(service, sample_production_order.id, sample_resource.id, "B-ACT-009")
        _confirm(service, batch.id, Decimal("9500"))
        _complete_batch(service, batch.id)

        session.refresh(sample_production_order)
        assert sample_production_order.status == "CREATED"
        assert sample_production_order.actual_quantity is None

        service.update_order_status(sample_production_order.id, ProductionOrderStatus.RELEASED)
        service.update_order_status(sample_production_order.id, ProductionOrderStatus.IN_PROCESS)
        service.update_order_status(sample_production_order.id, ProductionOrderStatus.COMPLETED)

        session.refresh(sample_production_order)
        assert sample_production_order.status == "COMPLETED"
        assert sample_production_order.actual_quantity == Decimal("9500.000")

    def test_sum_only_available_actuals(
        self, session, sample_production_order, sample_resource
    ):
        service = ProductionService(session)
        service.update_order_status(sample_production_order.id, ProductionOrderStatus.RELEASED)
        service.update_order_status(sample_production_order.id, ProductionOrderStatus.IN_PROCESS)
        b1 = _create_batch(service, sample_production_order.id, sample_resource.id, "B-ACT-010")
        b2 = _create_batch(service, sample_production_order.id, sample_resource.id, "B-ACT-011")
        _confirm(service, b1.id, Decimal("9500"))
        _complete_batch(service, b1.id)
        _complete_batch(service, b2.id)  # sem confirmação final

        session.refresh(sample_production_order)
        assert sample_production_order.status == "COMPLETED"
        assert sample_production_order.actual_quantity == Decimal("9500.000")


class TestConsolidationRollback:
    def test_handler_failure_rolls_back_status_and_actuals(
        self, session, sample_production_order, sample_resource
    ):
        def failing_handler(session, batch):
            raise RuntimeError("batch completed handler failed")

        service = ProductionService(session)
        batch = _create_batch(service, sample_production_order.id, sample_resource.id, "B-ACT-FAIL")
        _confirm(service, batch.id, Decimal("9500"))
        service.update_batch_status(batch.id, BatchStatus.IN_PRODUCTION)

        event_bus.subscribe(EVENT_BATCH_COMPLETED, failing_handler)
        try:
            with pytest.raises(RuntimeError):
                service.update_batch_status(batch.id, BatchStatus.COMPLETED)
        finally:
            event_bus.unsubscribe(EVENT_BATCH_COMPLETED, failing_handler)

        session.refresh(batch)
        assert batch.status == "IN_PRODUCTION"
        assert batch.actual_quantity is None
        assert batch.yield_percent is None