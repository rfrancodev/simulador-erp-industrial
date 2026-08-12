"""Tests for cascade delete relationships (L-14, L-26)."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.entities import (
    Batch,
    MaterialConsumption,
    NonConformity,
    ProductionConfirmation,
    QualityInspection,
)


def _add_batch(session: Session, order_id: int, resource_id: int, number: str) -> Batch:
    batch = Batch(
        batch_number=number,
        production_order_id=order_id,
        resource_id=resource_id,
        planned_quantity=Decimal("1000"),
        status="CREATED",
    )
    session.add(batch)
    session.flush()
    return batch


def test_delete_order_cascades_to_batches_inspections_and_non_conformities(
    session: Session, sample_production_order, sample_resource
):
    batch = _add_batch(session, sample_production_order.id, sample_resource.id, "B-CASCADE-1")

    inspection = QualityInspection(batch_id=batch.id, inspection_lot="QI-CASCADE-1")
    session.add(inspection)
    session.flush()

    nc = NonConformity(
        inspection_id=inspection.id,
        defect_type="OFF_SPEC",
        defect_code="NC-CAS-1",
        description="defect",
        severity="MAJOR",
        disposition="REWORK",
    )
    session.add(nc)
    session.flush()

    session.delete(sample_production_order)
    session.flush()

    assert session.get(Batch, batch.id) is None
    assert session.get(QualityInspection, inspection.id) is None
    assert session.get(NonConformity, nc.id) is None


def test_delete_order_cascades_to_confirmations_and_consumptions(
    session: Session, sample_production_order, sample_resource, sample_material
):
    batch = _add_batch(session, sample_production_order.id, sample_resource.id, "B-CASCADE-2")

    now = datetime.now(UTC)
    confirmation = ProductionConfirmation(
        batch_id=batch.id,
        operation="MIX",
        quantity=Decimal("100"),
        unit="L",
        confirmation_time=now,
    )
    session.add(confirmation)

    consumption = MaterialConsumption(
        batch_id=batch.id,
        material_id=sample_material.id,
        quantity=Decimal("50"),
        unit="KG",
        consumption_time=now,
    )
    session.add(consumption)
    session.flush()

    session.delete(sample_production_order)
    session.flush()

    assert session.get(Batch, batch.id) is None
    assert session.get(ProductionConfirmation, confirmation.id) is None
    assert session.get(MaterialConsumption, consumption.id) is None
