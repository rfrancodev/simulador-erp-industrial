"""Tests for the simulation engine (TASK-010)."""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.entities import (
    Base,
    Batch,
    CostRecord,
    Material,
    ProductionOrder,
    ProductionRecipe,
    QualityInspection,
    User,
)
from app.simulation.config import SimulationConfig, add_months, to_decimal
from app.simulation.engine import SimulationEngine


def _build_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_connection, connection_record):
        dbapi_connection.execute("pragma foreign_keys=ON")

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session():
    engine = _build_engine()
    SessionLocal = sessionmaker(bind=engine)
    s = SessionLocal()
    yield s
    s.close()


def _run(session, **overrides):
    config = SimulationConfig(months=1, seed=42, orders_per_month=5, **overrides)
    return SimulationEngine(session, config).run()


def _run_fresh(**overrides):
    engine = _build_engine()
    SessionLocal = sessionmaker(bind=engine)
    s = SessionLocal()
    config = SimulationConfig(months=1, seed=42, orders_per_month=5, **overrides)
    summary = SimulationEngine(s, config).run()
    order_numbers = list(
        s.scalars(select(ProductionOrder.order_number).order_by(ProductionOrder.order_number))
    )
    s.close()
    return summary, order_numbers


class TestConfig:
    def test_from_env_reads_vars(self, monkeypatch):
        monkeypatch.setenv("SIM_FAILURE_RATE", "0.10")
        monkeypatch.setenv("SIM_YIELD_MEAN", "0.90")
        config = SimulationConfig.from_env()
        assert config.production_failure_rate == 0.10
        assert config.yield_mean == 0.90

    def test_to_decimal_rounds_half_up(self):
        assert to_decimal(1.23456, 2) == Decimal("1.23")
        assert to_decimal(1.235, 2) == Decimal("1.24")

    def test_to_decimal_rejects_non_finite(self):
        with pytest.raises(ValueError):
            to_decimal(float("nan"), 2)
        with pytest.raises(ValueError):
            to_decimal(float("inf"), 2)

    def test_from_env_invalid_value_raises(self, monkeypatch):
        monkeypatch.setenv("SIM_MONTHS", "not-a-number")
        with pytest.raises(ValueError):
            SimulationConfig.from_env()

    def test_add_months_clamps_day(self):
        assert add_months(datetime(2026, 1, 31), 1) == datetime(2026, 2, 28)
        assert add_months(datetime(2026, 1, 15), 1) == datetime(2026, 2, 15)
        assert add_months(datetime(2026, 12, 1), 1) == datetime(2027, 1, 1)


class TestSimulationEngine:
    def test_generates_expected_volumes(self, session):
        summary = _run(session)
        assert summary.materials == 11  # 5 raw + 3 packaging + 3 finished
        assert summary.recipes == 3
        assert summary.resources == 5
        assert summary.orders == 5
        assert summary.batches >= 5
        assert summary.inspections == summary.batches
        assert summary.cost_records == 5
        assert summary.confirmations > 0
        assert summary.consumptions > 0
        assert summary.total_records() > 0

    def test_orders_are_completed_with_actual_quantity(self, session):
        _run(session)
        orders = list(session.scalars(select(ProductionOrder)))
        assert len(orders) == 5
        for order in orders:
            assert order.status == "COMPLETED"
            assert order.actual_quantity is not None and order.actual_quantity > 0
            assert order.actual_end is not None

    def test_each_batch_has_exactly_one_inspection(self, session):
        _run(session)
        batches = list(session.scalars(select(Batch)))
        assert len(batches) > 0
        for batch in batches:
            inspections = list(
                session.scalars(
                    select(QualityInspection).where(QualityInspection.batch_id == batch.id)
                )
            )
            assert len(inspections) == 1
            assert inspections[0].inspection_status in ("PASSED", "FAILED")

    def test_cost_records_are_consistent(self, session):
        _run(session)
        records = list(session.scalars(select(CostRecord)))
        assert len(records) == 5
        for record in records:
            planned = (
                record.planned_material_cost
                + record.planned_labor_cost
                + record.planned_machine_cost
                + record.planned_energy_cost
            )
            actual = (
                record.actual_material_cost
                + record.actual_labor_cost
                + record.actual_machine_cost
                + record.actual_energy_cost
            )
            assert record.planned_total_cost == planned
            assert record.actual_total_cost == actual

    def test_recipes_have_bom_and_routing(self, session):
        _run(session)
        recipes = list(session.scalars(select(ProductionRecipe)))
        assert len(recipes) == 3
        for recipe in recipes:
            assert len(recipe.components) == 7
            assert len(recipe.operations) == 5

    def test_deterministic_with_seed(self):
        summary1, orders1 = _run_fresh()
        summary2, orders2 = _run_fresh()
        assert orders1 == orders2
        assert summary1.orders == summary2.orders
        assert summary1.batches == summary2.batches
        assert summary1.inspections == summary2.inspections

    def test_crisis_scenario_increases_failures(self):
        def count_failed(scenario):
            engine = _build_engine()
            SessionLocal = sessionmaker(bind=engine)
            s = SessionLocal()
            config = SimulationConfig(months=12, seed=42, orders_per_month=10, scenario=scenario)
            SimulationEngine(s, config).run()
            failed = s.scalar(
                select(func.count())
                .select_from(QualityInspection)
                .where(QualityInspection.inspection_status == "FAILED")
            )
            s.close()
            return failed

        assert count_failed("crisis") > count_failed("normal")


class TestResetDomainData:
    def test_preserves_users_and_clears_domain_tables(self, session):
        from scripts.reset_database import reset_domain_data

        session.add(
            User(username="audit-user", password_hash="x", role="admin", is_active=True)
        )
        session.add(
            Material(
                material_code="MAT-RESET",
                material_name="Reset Material",
                material_type="FINISHED_PRODUCT",
                base_unit="L",
                plant="P001",
            )
        )
        session.commit()

        reset_domain_data(session)

        assert session.scalar(select(User).where(User.username == "audit-user")) is not None
        assert session.scalar(select(func.count()).select_from(Material)) == 0
