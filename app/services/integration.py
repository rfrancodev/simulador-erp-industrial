"""Cross-module integration handlers — PP-PI -> QM -> CO (plano/08).

The production/quality services publish domain events through the shared
``EventBus``; these handlers react by creating/updating dependent records in the
SAME transaction:

- ``batch.created``      -> auto-create a pending Quality Inspection (QM gate)
- ``order.completed``    -> auto-create a planned Cost Record (CO)
- ``inspection.failed``  -> apply a rework cost to the order's Cost Record (QM -> CO)

Handlers are idempotent (they no-op if the record already exists / was already
updated) and use repositories (flush-only), so the publishing service's
``commit()`` persists everything atomically.
"""

from __future__ import annotations

from decimal import Decimal
from logging import getLogger

from sqlalchemy import select

from app.core.events import (
    EVENT_BATCH_CREATED,
    EVENT_INSPECTION_FAILED,
    EVENT_ORDER_COMPLETED,
    event_bus,
)
from app.domain.costing.cost import CostRecordCreate
from app.domain.entities import Batch, QualityInspection
from app.domain.quality.inspection import InspectionStatus, QualityInspectionCreate
from app.repositories.costing_repository import CostRecordRepository
from app.repositories.quality_repository import QualityInspectionRepository

logger = getLogger(__name__)

# Default planned cost estimates (R$ per liter) used for auto-generated cost
# records. These are synthetic placeholders (NOT derived from the recipe BOM),
# refined later via the CO API. The simulation engine (TASK-010) computes
# material cost from the BOM with per-material unit prices instead.
_MATERIAL_PER_L = Decimal("1.60")
_LABOR_PER_L = Decimal("0.35")
_MACHINE_PER_L = Decimal("0.30")
_ENERGY_PER_L = Decimal("0.18")

# Extra cost factor applied when a quality inspection fails (rework/scrap).
_REWORK_COST_FACTOR = Decimal("0.08")

_registered = False


def register_integration_handlers() -> None:
    """Register the PP-PI -> QM / CO handlers on the shared event bus (idempotent)."""
    global _registered
    if _registered:
        return
    _registered = True
    event_bus.subscribe(EVENT_BATCH_CREATED, _auto_create_inspection)
    event_bus.subscribe(EVENT_ORDER_COMPLETED, _auto_create_cost_record)
    event_bus.subscribe(EVENT_INSPECTION_FAILED, _on_inspection_failed)


def _auto_create_inspection(session, batch) -> None:
    repo = QualityInspectionRepository(session)
    if repo.get_by_batch(batch.id) is not None:
        return
    inspection_lot = f"QI-{batch.id:012d}"
    repo.create(QualityInspectionCreate(batch_id=batch.id, inspection_lot=inspection_lot))
    logger.info("Auto-created quality inspection %s for batch %s", inspection_lot, batch.batch_number)


def _auto_create_cost_record(session, order) -> None:
    repo = CostRecordRepository(session)
    if repo.get_by_order(order.id) is not None:
        return
    qty = order.planned_quantity
    data = CostRecordCreate(
        production_order_id=order.id,
        planned_material_cost=(qty * _MATERIAL_PER_L).quantize(Decimal("0.01")),
        planned_labor_cost=(qty * _LABOR_PER_L).quantize(Decimal("0.01")),
        planned_machine_cost=(qty * _MACHINE_PER_L).quantize(Decimal("0.01")),
        planned_energy_cost=(qty * _ENERGY_PER_L).quantize(Decimal("0.01")),
    )
    repo.create_for_order(order.id, data)
    logger.info("Auto-created cost record for order %s", order.order_number)

    # If a quality inspection already failed, apply the rework impact now.
    if _order_has_failed_inspection(session, order.id):
        _apply_rework_to_order(session, order.id)


def _on_inspection_failed(session, inspection) -> None:
    batch = session.get(Batch, inspection.batch_id)
    if batch is None:
        return
    _apply_rework_to_order(session, batch.production_order_id)
    logger.info("Applied rework cost after inspection %s failed", inspection.inspection_lot)


def _order_has_failed_inspection(session, order_id: int) -> bool:
    stmt = (
        select(QualityInspection.id)
        .join(Batch, QualityInspection.batch_id == Batch.id)
        .where(
            Batch.production_order_id == order_id,
            QualityInspection.inspection_status == InspectionStatus.FAILED.value,
        )
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none() is not None


def _apply_rework_to_order(session, order_id: int) -> None:
    """Apply a rework cost factor to the order's cost record (idempotent)."""
    repo = CostRecordRepository(session)
    record = repo.get_by_order(order_id)
    if record is None or record.actual_total_cost is not None:
        return

    factor = Decimal("1") + _REWORK_COST_FACTOR
    record.actual_material_cost = (record.planned_material_cost * factor).quantize(Decimal("0.01"))
    record.actual_labor_cost = (record.planned_labor_cost * factor).quantize(Decimal("0.01"))
    record.actual_machine_cost = (record.planned_machine_cost * factor).quantize(Decimal("0.01"))
    record.actual_energy_cost = (record.planned_energy_cost * factor).quantize(Decimal("0.01"))
    record.actual_total_cost = (
        record.actual_material_cost
        + record.actual_labor_cost
        + record.actual_machine_cost
        + record.actual_energy_cost
    )
    session.flush()
