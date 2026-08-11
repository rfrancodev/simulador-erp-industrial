"""Unit tests for Cost Record domain model."""

from decimal import Decimal

import pytest

from app.domain.costing.cost import CostRecordCreate, CostRecordUpdate
from app.domain.entities import CostRecord


class TestCostRecordModel:
    def test_cost_record_variance_none_when_no_actual(self, session, sample_production_order):
        cost = CostRecord(
            production_order_id=sample_production_order.id,
            planned_material_cost=Decimal("10000"),
            planned_labor_cost=Decimal("2000"),
            planned_machine_cost=Decimal("5000"),
            planned_energy_cost=Decimal("1000"),
            planned_total_cost=Decimal("18000"),
        )
        session.add(cost)
        session.flush()
        assert cost.variance is None
        assert cost.variance_percent is None

    def test_cost_record_variance_positive(self, session, sample_production_order):
        cost = CostRecord(
            production_order_id=sample_production_order.id,
            planned_material_cost=Decimal("10000"),
            planned_labor_cost=Decimal("2000"),
            planned_machine_cost=Decimal("5000"),
            planned_energy_cost=Decimal("1000"),
            planned_total_cost=Decimal("18000"),
            actual_material_cost=Decimal("11000"),
            actual_labor_cost=Decimal("2100"),
            actual_machine_cost=Decimal("5100"),
            actual_energy_cost=Decimal("1100"),
            actual_total_cost=Decimal("19300"),
        )
        session.add(cost)
        session.flush()
        assert cost.variance == Decimal("1300")
        assert float(cost.variance_percent) == pytest.approx(7.22, rel=0.01)

    def test_cost_record_variance_negative(self, session, sample_production_order):
        cost = CostRecord(
            production_order_id=sample_production_order.id,
            planned_material_cost=Decimal("10000"),
            planned_labor_cost=Decimal("3000"),
            planned_machine_cost=Decimal("4000"),
            planned_energy_cost=Decimal("1000"),
            planned_total_cost=Decimal("18000"),
            actual_material_cost=Decimal("10000"),
            actual_labor_cost=Decimal("2500"),
            actual_machine_cost=Decimal("3000"),
            actual_energy_cost=Decimal("1500"),
            actual_total_cost=Decimal("17000"),
        )
        session.add(cost)
        session.flush()
        assert cost.variance == Decimal("-1000")
        assert float(cost.variance_percent) == pytest.approx(-5.56, rel=0.01)


class TestCostRecordPydantic:
    def test_cost_record_create(self):
        record = CostRecordCreate(
            production_order_id=1,
            planned_material_cost=Decimal("10000"),
            planned_labor_cost=Decimal("2000"),
            planned_machine_cost=Decimal("5000"),
            planned_energy_cost=Decimal("1000"),
        )
        assert record.planned_material_cost == Decimal("10000")

    def test_cost_record_update_partial(self):
        update = CostRecordUpdate(actual_material_cost=Decimal("11000"))
        data = update.model_dump(exclude_unset=True)
        assert "actual_material_cost" in data
        assert data["actual_material_cost"] == Decimal("11000")
        assert "actual_labor_cost" not in data
