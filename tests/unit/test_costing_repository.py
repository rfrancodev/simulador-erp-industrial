"""Unit tests for CO — CostRecordRepository."""

from decimal import Decimal

from app.domain.costing.cost import CostRecordCreate, CostRecordUpdate
from app.repositories.costing_repository import CostRecordRepository


class TestCostRecordRepository:
    def test_create_for_order_calculates_total(self, session, sample_production_order):
        repo = CostRecordRepository(session)
        record = repo.create_for_order(
            order_id=sample_production_order.id,
            data=CostRecordCreate(
                production_order_id=sample_production_order.id,
                planned_material_cost=Decimal("10000"),
                planned_labor_cost=Decimal("2000"),
                planned_machine_cost=Decimal("5000"),
                planned_energy_cost=Decimal("1000"),
            ),
        )
        assert record.id is not None
        assert record.planned_total_cost == Decimal("18000")

    def test_get_by_order(self, session, sample_production_order):
        repo = CostRecordRepository(session)
        created = repo.create_for_order(
            order_id=sample_production_order.id,
            data=CostRecordCreate(
                production_order_id=sample_production_order.id,
                planned_material_cost=Decimal("10000"),
            ),
        )
        found = repo.get_by_order(sample_production_order.id)
        assert found is not None
        assert found.id == created.id

    def test_update_actual_recalculates_total(self, session, sample_production_order):
        repo = CostRecordRepository(session)
        created = repo.create_for_order(
            order_id=sample_production_order.id,
            data=CostRecordCreate(
                production_order_id=sample_production_order.id,
                planned_material_cost=Decimal("10000"),
                planned_labor_cost=Decimal("2000"),
                planned_machine_cost=Decimal("5000"),
                planned_energy_cost=Decimal("1000"),
            ),
        )
        updated = repo.update_actual(
            created.id,
            CostRecordUpdate(
                actual_material_cost=Decimal("11000"),
                actual_labor_cost=Decimal("2100"),
                actual_machine_cost=Decimal("5100"),
                actual_energy_cost=Decimal("1100"),
            ),
        )
        assert updated is not None
        assert updated.actual_total_cost == Decimal("19300")
        assert updated.variance == Decimal("1300")