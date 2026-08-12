"""Cross-module integration handlers — PP-PI -> QM -> CO (plano/08).

The production service publishes domain events through the shared ``EventBus``;
these handlers react by creating dependent records in the SAME transaction:

- ``batch.created``      -> auto-create a pending Quality Inspection (QM gate)
- ``order.completed``    -> auto-create a planned Cost Record (CO)

Handlers are idempotent (they no-op if the record already exists) and use
repositories (flush-only), so the publishing service's ``commit()`` persists
everything atomically.
"""

from __future__ import annotations

from decimal import Decimal
from logging import getLogger

from app.core.events import EVENT_BATCH_CREATED, EVENT_ORDER_COMPLETED, event_bus
from app.domain.costing.cost import CostRecordCreate
from app.domain.quality.inspection import QualityInspectionCreate
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

_registered = False


def register_integration_handlers() -> None:
    """Register the PP-PI -> QM / CO handlers on the shared event bus (idempotent)."""
    global _registered
    if _registered:
        return
    _registered = True
    event_bus.subscribe(EVENT_BATCH_CREATED, _auto_create_inspection)
    event_bus.subscribe(EVENT_ORDER_COMPLETED, _auto_create_cost_record)


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
