"""Unit tests for AnalyticsService and Dashboard API endpoints."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.analytics.service import AnalyticsService
from app.database.connection import session_dependency
from app.domain.entities import (
    Base,
    Batch,
    CostRecord,
    Material,
    ProductionOrder,
    ProductionRecipe,
    ProductionResource,
    QualityInspection,
)
from app.main import app
from app.simulation.config import SimulationConfig
from app.simulation.engine import SimulationEngine


@pytest.fixture
def engine():
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
def session(engine) -> Session:
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(session: Session):
    def override():
        yield session

    app.dependency_overrides[session_dependency] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _create_order(
    session, order_number, planned_start, actual_quantity, has_inspection,
    actual_total_cost=Decimal("210"),
    planned_quantity=Decimal("10000"),
    status="COMPLETED",
):
    """Create a full order (material/recipe/resource/order/batch + optional inspection + cost).

    ``actual_total_cost=None`` produces a ``CostRecord`` whose actual cost fields
    are NULL (matching SIM-ORD-0003 / SIM-ORD-0004).
    """
    material = Material(
        material_code=f"M-{order_number}",
        material_name="Test",
        material_type="FINISHED_PRODUCT",
        base_unit="L",
        plant="P001",
    )
    session.add(material)
    session.flush()
    recipe = ProductionRecipe(recipe_code=f"R-{order_number}", material_id=material.id, version="1.0")
    session.add(recipe)
    session.flush()
    resource = ProductionResource(
        resource_code=f"RES-{order_number}", resource_name="R", work_center="WC", resource_type="F"
    )
    session.add(resource)
    session.flush()
    order = ProductionOrder(
        order_number=order_number,
        material_id=material.id,
        recipe_id=recipe.id,
        planned_quantity=planned_quantity,
        planned_start=planned_start,
        planned_end=planned_start + timedelta(hours=8),
        status=status,
        actual_quantity=actual_quantity,
    )
    session.add(order)
    session.flush()
    batch = Batch(
        batch_number=f"B-{order_number}",
        production_order_id=order.id,
        resource_id=resource.id,
        planned_quantity=Decimal("10000"),
        actual_quantity=Decimal("9000"),
        status="COMPLETED",
    )
    session.add(batch)
    session.flush()
    if has_inspection:
        session.add(
            QualityInspection(
                batch_id=batch.id, inspection_lot=f"QI-{order_number}", inspection_status="PASSED"
            )
        )
    if actual_total_cost is not None:
        actual_material_cost = Decimal("110")
        actual_labor_cost = Decimal("50")
        actual_machine_cost = Decimal("30")
        actual_energy_cost = Decimal("20")
    else:
        actual_material_cost = None
        actual_labor_cost = None
        actual_machine_cost = None
        actual_energy_cost = None

    session.add(
        CostRecord(
            production_order_id=order.id,
            planned_material_cost=Decimal("100"),
            planned_labor_cost=Decimal("50"),
            planned_machine_cost=Decimal("30"),
            planned_energy_cost=Decimal("20"),
            planned_total_cost=Decimal("200"),
            actual_material_cost=actual_material_cost,
            actual_labor_cost=actual_labor_cost,
            actual_machine_cost=actual_machine_cost,
            actual_energy_cost=actual_energy_cost,
            actual_total_cost=actual_total_cost,
        )
    )
    session.commit()
    return order


def _create_oee_scenario(session, actual_quantity):
    """One completed order (no delay) + one batch + one passed inspection."""
    material = Material(
        material_code="M-OEE", material_name="OEE Material",
        material_type="FINISHED_PRODUCT", base_unit="L", plant="P001",
    )
    session.add(material)
    session.flush()
    recipe = ProductionRecipe(recipe_code="R-OEE", material_id=material.id, version="1.0")
    session.add(recipe)
    session.flush()
    resource = ProductionResource(
        resource_code="RES-OEE", resource_name="R", work_center="WC", resource_type="F"
    )
    session.add(resource)
    session.flush()
    start = datetime(2026, 1, 10, 8, 0, tzinfo=UTC)
    order = ProductionOrder(
        order_number="PO-OEE",
        material_id=material.id,
        recipe_id=recipe.id,
        planned_quantity=Decimal("10000"),
        planned_start=start,
        planned_end=start + timedelta(hours=8),
        actual_start=start,
        actual_end=start + timedelta(hours=8),
        status="COMPLETED",
    )
    session.add(order)
    session.flush()
    batch = Batch(
        batch_number="B-OEE",
        production_order_id=order.id,
        resource_id=resource.id,
        planned_quantity=Decimal("10000"),
        actual_quantity=actual_quantity,
        status="COMPLETED",
    )
    session.add(batch)
    session.flush()
    session.add(
        QualityInspection(batch_id=batch.id, inspection_lot="QI-OEE", inspection_status="PASSED")
    )
    session.commit()


class TestAnalyticsService:
    def test_executive_kpis_empty(self, session: Session):
        svc = AnalyticsService(session)
        kpis = svc.executive_kpis()
        assert kpis["production"]["total_volume_liters"] == 0
        assert kpis["production"]["active_orders"] == 0
        assert kpis["quality"]["total_inspections"] == 0
        assert kpis["quality"]["pass_rate"] == 0.0
        assert kpis["cost"]["total_planned_cost"] == 0.0
        assert kpis["orders"]["total_orders"] == 0

    def test_order_status_distribution_empty(self, session: Session):
        svc = AnalyticsService(session)
        result = svc.order_status_distribution()
        assert result == []

    def test_inspection_status_distribution_empty(self, session: Session):
        svc = AnalyticsService(session)
        result = svc.inspection_status_distribution()
        assert result == []

    def test_cost_variance_by_order_empty(self, session: Session):
        svc = AnalyticsService(session)
        result = svc.cost_variance_by_order()
        assert result == []

    def test_order_360_not_found(self, session: Session):
        svc = AnalyticsService(session)
        assert svc.order_360("NONEXISTENT") is None

    def test_order_360_with_actual_cost(self, session: Session):
        start = datetime(2026, 1, 10, 8, 0, tzinfo=UTC)
        _create_order(session, "SIM-ORD-0001", start, Decimal("9000"), True)
        data = AnalyticsService(session).order_360("SIM-ORD-0001")
        assert data["cost"]["actual_total"] == 210.0
        assert data["cost"]["planned_total"] == 200.0
        assert data["cost"]["variance"] == 10.0

    def test_order_360_without_actual_cost(self, session: Session):
        start = datetime(2026, 1, 10, 8, 0, tzinfo=UTC)
        _create_order(
            session, "SIM-ORD-0003", start, Decimal("9000"), True, actual_total_cost=None
        )
        data = AnalyticsService(session).order_360("SIM-ORD-0003")
        assert data["cost"]["actual_total"] is None
        assert data["cost"]["variance"] is None
        assert data["cost"]["variance_percent"] is None

    def test_production_stats_empty(self, session: Session):
        svc = AnalyticsService(session)
        stats = svc.production_stats()
        assert stats["materials_count"] == 0
        assert stats["recipes_count"] == 0
        assert stats["resources_count"] == 0
        assert stats["recent_orders"] == []

    def test_production_stats_pagination(self, session: Session):
        start = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
        for i in range(5):
            _create_order(
                session,
                f"PO-PG-{i:04d}",
                start + timedelta(days=i),
                Decimal("9000"),
                has_inspection=False,
            )
        svc = AnalyticsService(session)

        stats = svc.production_stats(page=1, per_page=2)
        assert stats["total_orders"] == 5
        assert stats["total_pages"] == 3
        assert stats["page"] == 1
        assert [o["order_number"] for o in stats["recent_orders"]] == [
            "PO-PG-0004",
            "PO-PG-0003",
        ]

        stats2 = svc.production_stats(page=2, per_page=2)
        assert stats2["page"] == 2
        assert [o["order_number"] for o in stats2["recent_orders"]] == [
            "PO-PG-0002",
            "PO-PG-0001",
        ]

        stats3 = svc.production_stats(page=99, per_page=2)
        assert stats3["page"] == 3
        assert [o["order_number"] for o in stats3["recent_orders"]] == ["PO-PG-0000"]

    def test_production_stats_filter_by_order_partial(self, session: Session):
        start = datetime(2026, 1, 10, 8, 0, tzinfo=UTC)
        _create_order(session, "SIM-ORD-0001", start, Decimal("9000"), False)
        _create_order(session, "SIM-ORD-0002", start, Decimal("9000"), False)
        _create_order(session, "OTHER-0001", start, Decimal("9000"), False)
        stats = AnalyticsService(session).production_stats(order="SIM-ORD")
        assert stats["total_orders"] == 2
        assert {o["order_number"] for o in stats["recent_orders"]} == {
            "SIM-ORD-0001",
            "SIM-ORD-0002",
        }

    def test_production_stats_filter_by_status(self, session: Session):
        start = datetime(2026, 1, 10, 8, 0, tzinfo=UTC)
        _create_order(session, "PO-A", start, Decimal("9000"), False, status="COMPLETED")
        _create_order(session, "PO-B", start, Decimal("9000"), False, status="COMPLETED")
        _create_order(session, "PO-C", start, Decimal("9000"), False, status="IN_PROCESS")
        stats = AnalyticsService(session).production_stats(status="IN_PROCESS")
        assert stats["total_orders"] == 1
        assert [o["order_number"] for o in stats["recent_orders"]] == ["PO-C"]

    def test_production_stats_filter_by_planned_start(self, session: Session):
        _create_order(session, "PO-JAN", datetime(2026, 1, 10, 8, 0, tzinfo=UTC), Decimal("9000"), False)
        _create_order(session, "PO-MAR", datetime(2026, 3, 10, 8, 0, tzinfo=UTC), Decimal("9000"), False)
        _create_order(session, "PO-MAY", datetime(2026, 5, 10, 8, 0, tzinfo=UTC), Decimal("9000"), False)
        svc = AnalyticsService(session)
        stats = svc.production_stats(
            planned_start_from=date(2026, 3, 1), planned_start_to=date(2026, 3, 31)
        )
        assert stats["total_orders"] == 1
        assert [o["order_number"] for o in stats["recent_orders"]] == ["PO-MAR"]

    def test_production_stats_filter_by_planned_quantity(self, session: Session):
        start = datetime(2026, 1, 10, 8, 0, tzinfo=UTC)
        _create_order(session, "PO-1", start, Decimal("9000"), False, planned_quantity=Decimal("5000"))
        _create_order(session, "PO-2", start, Decimal("9000"), False, planned_quantity=Decimal("10000"))
        _create_order(session, "PO-3", start, Decimal("9000"), False, planned_quantity=Decimal("15000"))
        stats = AnalyticsService(session).production_stats(
            planned_min=Decimal("8000"), planned_max=Decimal("12000")
        )
        assert stats["total_orders"] == 1
        assert [o["order_number"] for o in stats["recent_orders"]] == ["PO-2"]

    def test_production_stats_filter_by_actual_quantity(self, session: Session):
        start = datetime(2026, 1, 10, 8, 0, tzinfo=UTC)
        _create_order(session, "PO-1", start, Decimal("4000"), False)
        _create_order(session, "PO-2", start, Decimal("9000"), False)
        _create_order(session, "PO-3", start, Decimal("15000"), False)
        stats = AnalyticsService(session).production_stats(
            actual_min=Decimal("8000"), actual_max=Decimal("12000")
        )
        assert stats["total_orders"] == 1
        assert [o["order_number"] for o in stats["recent_orders"]] == ["PO-2"]

    def test_production_stats_combined_filters(self, session: Session):
        start = datetime(2026, 1, 10, 8, 0, tzinfo=UTC)
        _create_order(session, "SIM-ORD-0001", start, Decimal("9000"), False, status="COMPLETED")
        _create_order(session, "SIM-ORD-0002", start, Decimal("9000"), False, status="IN_PROCESS")
        _create_order(session, "OTHER-0001", start, Decimal("9000"), False, status="COMPLETED")
        stats = AnalyticsService(session).production_stats(order="SIM-ORD", status="COMPLETED")
        assert stats["total_orders"] == 1
        assert [o["order_number"] for o in stats["recent_orders"]] == ["SIM-ORD-0001"]

    def test_production_stats_pagination_preserves_filters(self, session: Session):
        start = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
        for i in range(5):
            _create_order(session, f"SIM-ORD-{i:04d}", start + timedelta(days=i), Decimal("9000"), False)
        svc = AnalyticsService(session)
        stats = svc.production_stats(page=2, per_page=2, order="SIM-ORD")
        assert stats["total_orders"] == 5
        assert stats["total_pages"] == 3
        assert stats["page"] == 2
        assert [o["order_number"] for o in stats["recent_orders"]] == [
            "SIM-ORD-0002",
            "SIM-ORD-0001",
        ]

    def test_materials_recipes_resources_datasets(self, session: Session):
        start = datetime(2026, 1, 10, 8, 0, tzinfo=UTC)
        _create_order(session, "PO-1", start, Decimal("9000"), True)
        svc = AnalyticsService(session)

        materials = svc.materials()
        assert len(materials) == 1
        assert materials[0]["code"] == "M-PO-1"
        assert materials[0]["unit"] == "L"

        recipes = svc.recipes()
        assert len(recipes) == 1
        assert recipes[0]["code"] == "R-PO-1"
        assert recipes[0]["product"] == "Test"

        resources = svc.resources()
        assert len(resources) == 1
        assert resources[0]["code"] == "RES-PO-1"

    def test_non_conformities_and_pending_inspections_datasets(self, session: Session):
        from app.domain.entities import NonConformity

        start = datetime(2026, 1, 10, 8, 0, tzinfo=UTC)
        _create_order(session, "PO-1", start, Decimal("9000"), True)

        # Attach a pending inspection to a second order (the helper only creates
        # a PASSED inspection when requested).
        material = Material(
            material_code="M-PO-2", material_name="Test2", material_type="RAW_MATERIAL",
            base_unit="L", plant="P001",
        )
        session.add(material)
        session.flush()
        recipe = ProductionRecipe(recipe_code="R-PO-2", material_id=material.id, version="1.0")
        session.add(recipe)
        session.flush()
        resource = ProductionResource(
            resource_code="RES-PO-2", resource_name="R2", work_center="WC", resource_type="F"
        )
        session.add(resource)
        session.flush()
        order = ProductionOrder(
            order_number="PO-2", material_id=material.id, recipe_id=recipe.id,
            planned_quantity=Decimal("10000"), planned_start=start,
            planned_end=start + timedelta(hours=8), status="COMPLETED",
        )
        session.add(order)
        session.flush()
        batch = Batch(
            batch_number="B-PO-2", production_order_id=order.id, resource_id=resource.id,
            planned_quantity=Decimal("10000"), status="COMPLETED",
        )
        session.add(batch)
        session.flush()
        session.add(
            QualityInspection(
                batch_id=batch.id, inspection_lot="QI-PO-2", inspection_status="PENDING"
            )
        )
        session.commit()

        svc = AnalyticsService(session)
        pending = svc.pending_inspections()
        assert len(pending) == 1
        assert pending[0]["order_number"] == "PO-2"
        assert pending[0]["batch_number"] == "B-PO-2"
        assert pending[0]["inspection_lot"] == "QI-PO-2"

        # There is a PASSED inspection on PO-1, so no pending record.
        assert all(p["inspection_lot"] != "QI-PO-1" for p in pending)

        # Add a non-conformity against the pending inspection.
        inspection = session.query(QualityInspection).filter_by(inspection_lot="QI-PO-2").one()
        session.add(
            NonConformity(
                inspection_id=inspection.id,
                defect_type="Crack",
                defect_code="D-01",
                description="Cracked bottle",
                severity="MAJOR",
                disposition="REWORK",
            )
        )
        session.commit()

        ncs = svc.non_conformities()
        assert len(ncs) == 1
        assert ncs[0]["order_number"] == "PO-2"
        assert ncs[0]["inspection_lot"] == "QI-PO-2"
        assert ncs[0]["defect_code"] == "D-01"
        assert ncs[0]["disposition"] == "REWORK"

    def test_production_page_pagination(self, client: TestClient, session: Session):
        start = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
        for i in range(5):
            _create_order(
                session,
                f"PO-PG-{i:04d}",
                start + timedelta(days=i),
                Decimal("9000"),
                has_inspection=False,
            )

        resp = client.get("/dashboard/production?page=1&per_page=2")
        assert resp.status_code == 200
        assert "Page 1 of 3" in resp.text
        assert "PO-PG-0004" in resp.text
        assert "Próxima" in resp.text

        resp2 = client.get("/dashboard/production?page=2&per_page=2")
        assert resp2.status_code == 200
        assert "Page 2 of 3" in resp2.text
        assert "PO-PG-0001" in resp2.text
        assert "Anterior" in resp2.text

        resp3 = client.get("/dashboard/production?page=3&per_page=2")
        assert resp3.status_code == 200
        assert "Page 3 of 3" in resp3.text
        assert "PO-PG-0000" in resp3.text

    def test_quality_stats_empty(self, session: Session):
        svc = AnalyticsService(session)
        stats = svc.quality_stats()
        assert stats["pending_inspections"] == 0
        assert stats["recent_inspections"] == []

    def test_cost_stats_empty(self, session: Session):
        svc = AnalyticsService(session)
        stats = svc.cost_stats()
        assert stats["cost_by_material"] == []

    def test_monthly_trend_empty(self, session: Session):
        svc = AnalyticsService(session)
        assert svc.monthly_trend() == []

    def test_oee_empty(self, session: Session):
        svc = AnalyticsService(session)
        oee = svc.oee()
        assert oee["oee"] == 0.0
        assert oee["availability"] == 0.0

    def test_machine_utilization_empty(self, session: Session):
        assert AnalyticsService(session).machine_utilization() == 0.0

    def test_cost_per_liter_empty(self, session: Session):
        assert AnalyticsService(session).cost_per_liter() == 0.0

    def test_quality_cost_empty(self, session: Session):
        assert AnalyticsService(session).quality_cost() == 0.0

    def test_advanced_indicators_with_simulated_data(self, session: Session):
        SimulationEngine(session, SimulationConfig(months=1, seed=42, orders_per_month=5)).run()
        svc = AnalyticsService(session)
        oee = svc.oee()
        assert 0 <= oee["oee"] <= 100
        assert 0 <= oee["availability"] <= 100
        assert 0 < svc.machine_utilization() <= 100
        assert svc.cost_per_liter() > 0
        assert svc.quality_cost() >= 0

    def test_oee_expected_values(self, session: Session):
        _create_oee_scenario(session, Decimal("9600"))
        oee = AnalyticsService(session).oee()
        assert oee["availability"] == 100.0  # no delay
        assert oee["performance"] == 96.0  # 9600 / 10000
        assert oee["quality"] == 100.0  # all passed
        assert oee["oee"] == 96.0  # 1.0 * 0.96 * 1.0

    def test_oee_clamped_at_100(self, session: Session):
        _create_oee_scenario(session, Decimal("11000"))  # overproduction
        oee = AnalyticsService(session).oee()
        assert oee["performance"] == 110.0
        assert oee["oee"] == 100.0  # clamped

    def test_monthly_trend_with_simulated_data(self, session: Session):
        SimulationEngine(session, SimulationConfig(months=2, seed=42, orders_per_month=3)).run()
        trend = AnalyticsService(session).monthly_trend()
        assert len(trend) == 2
        assert trend[0]["month"] == "2026-01"
        assert trend[1]["month"] == "2026-02"
        for bucket in trend:
            assert bucket["orders"] == 3
            assert bucket["volume_liters"] > 0
            assert bucket["planned_cost"] > 0
            assert bucket["actual_cost"] > 0
            assert 0 <= bucket["pass_rate"] <= 100

    def test_monthly_trend_falls_back_to_planned_quantity(self, session: Session):
        start = datetime(2026, 1, 10, tzinfo=UTC)
        _create_order(session, "PO-1", start, actual_quantity=None, has_inspection=True)
        trend = AnalyticsService(session).monthly_trend()
        assert trend[0]["volume_liters"] == 10000.0

    def test_monthly_trend_order_without_inspection(self, session: Session):
        start = datetime(2026, 1, 10, tzinfo=UTC)
        _create_order(session, "PO-1", start, actual_quantity=Decimal("9000"), has_inspection=False)
        trend = AnalyticsService(session).monthly_trend()
        assert trend[0]["pass_rate"] == 0.0

    def test_monthly_trend_spans_year_boundary_ordered(self, session: Session):
        _create_order(
            session, "PO-DEC", datetime(2025, 12, 15, tzinfo=UTC), Decimal("9000"), True
        )
        _create_order(
            session, "PO-JAN", datetime(2026, 1, 15, tzinfo=UTC), Decimal("9000"), True
        )
        trend = AnalyticsService(session).monthly_trend()
        assert [b["month"] for b in trend] == ["2025-12", "2026-01"]


class TestDashboardAPI:
    @pytest.mark.no_auth
    def test_home_page_requires_authentication(self, client: TestClient):
        assert client.get("/dashboard/").status_code == 401

    @pytest.mark.no_auth
    def test_dashboard_login_sets_cookie_and_grants_access(self, client: TestClient, session: Session):
        from app.domain.auth import UserCreate, UserRole
        from app.services.auth_service import AuthService

        AuthService(session).create_user(
            UserCreate(username="dashadmin", password="secret123", role=UserRole.ADMIN)
        )

        login = client.post(
            "/dashboard/login",
            data={"username": "dashadmin", "password": "secret123"},
            follow_redirects=False,
        )
        assert login.status_code == 303
        assert "access_token" in login.cookies

        token = login.cookies["access_token"]
        home = client.get("/dashboard/", headers={"Cookie": f"access_token={token}"})
        assert home.status_code == 200
        assert "Dashboard Executivo" in home.text

    @pytest.mark.no_auth
    def test_dashboard_login_wrong_password_is_rejected(self, client: TestClient):
        login = client.post(
            "/dashboard/login",
            data={"username": "nobody", "password": "wrong"},
        )
        assert login.status_code == 401
        assert "access_token" not in login.cookies

    @pytest.mark.no_auth
    def test_dashboard_login_cookie_secure_flag(self, client: TestClient, session: Session, monkeypatch):
        from app.domain.auth import UserCreate, UserRole
        from app.services.auth_service import AuthService

        AuthService(session).create_user(
            UserCreate(username="secureadmin", password="secret123", role=UserRole.ADMIN)
        )

        monkeypatch.setenv("COOKIE_SECURE", "true")
        login = client.post(
            "/dashboard/login",
            data={"username": "secureadmin", "password": "secret123"},
            follow_redirects=False,
        )
        assert login.status_code == 303
        assert "Secure" in login.headers.get("set-cookie", "")

        monkeypatch.setenv("COOKIE_SECURE", "false")
        login2 = client.post(
            "/dashboard/login",
            data={"username": "secureadmin", "password": "secret123"},
            follow_redirects=False,
        )
        assert login2.status_code == 303
        assert "Secure" not in login2.headers.get("set-cookie", "")

    def test_home_page_renders(self, client: TestClient):
        resp = client.get("/dashboard/")
        assert resp.status_code == 200
        assert "Dashboard Executivo" in resp.text
        assert "Industrial ERP Simulator" in resp.text

    def test_order_360_page_renders(self, client: TestClient):
        resp = client.get("/dashboard/order-360")
        assert resp.status_code == 200
        assert "Order 360" in resp.text

    def test_production_page_renders(self, client: TestClient):
        resp = client.get("/dashboard/production")
        assert resp.status_code == 200
        assert "Production" in resp.text
        assert "Recent Production Orders" in resp.text

    def test_quality_page_renders(self, client: TestClient):
        resp = client.get("/dashboard/quality")
        assert resp.status_code == 200
        assert "Quality" in resp.text
        assert "Recent Inspections" in resp.text

    def test_costing_page_renders(self, client: TestClient):
        resp = client.get("/dashboard/costing")
        assert resp.status_code == 200
        assert "Cost" in resp.text
        assert "Cost by Material" in resp.text

    def test_api_kpis(self, client: TestClient):
        resp = client.get("/api/dashboard/kpis")
        assert resp.status_code == 200
        data = resp.json()
        assert "production" in data
        assert "quality" in data
        assert "cost" in data
        assert "orders" in data

    def test_api_order_360_not_found(self, client: TestClient):
        resp = client.get("/api/dashboard/order-360/NONEXISTENT")
        assert resp.status_code == 404

    def test_api_order_360_handles_null_actual_total(self, client: TestClient, session: Session):
        start = datetime(2026, 1, 10, 8, 0, tzinfo=UTC)
        _create_order(session, "SIM-ORD-0001", start, Decimal("9000"), True, Decimal("210"))
        _create_order(session, "SIM-ORD-0002", start, Decimal("9000"), True, Decimal("210"))
        _create_order(session, "SIM-ORD-0003", start, Decimal("9000"), True, None)
        _create_order(session, "SIM-ORD-0004", start, Decimal("9000"), True, None)

        responses = {
            number: client.get(f"/api/dashboard/order-360/{number}")
            for number in ("SIM-ORD-0001", "SIM-ORD-0002", "SIM-ORD-0003", "SIM-ORD-0004")
        }

        for number, resp in responses.items():
            assert resp.status_code == 200, f"{number} returned {resp.status_code}"

        assert responses["SIM-ORD-0001"].json()["cost"]["actual_total"] == 210.0
        assert responses["SIM-ORD-0002"].json()["cost"]["actual_total"] == 210.0
        assert responses["SIM-ORD-0003"].json()["cost"]["actual_total"] is None
        assert responses["SIM-ORD-0004"].json()["cost"]["actual_total"] is None

    def test_api_production_stats(self, client: TestClient):
        resp = client.get("/api/dashboard/production-stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "materials_count" in data

    def test_api_quality_stats(self, client: TestClient):
        resp = client.get("/api/dashboard/quality-stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "pending_inspections" in data

    def test_api_cost_stats(self, client: TestClient):
        resp = client.get("/api/dashboard/cost-stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "cost_by_material" in data

    def test_api_monthly_trend(self, client: TestClient):
        resp = client.get("/api/dashboard/monthly-trend")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_api_modal_datasets(self, client: TestClient, session: Session):
        start = datetime(2026, 1, 10, 8, 0, tzinfo=UTC)
        _create_order(session, "PO-1", start, Decimal("9000"), True)

        for path in ("materials", "recipes", "resources", "non-conformities", "pending-inspections"):
            resp = client.get(f"/api/dashboard/{path}")
            assert resp.status_code == 200, path
            assert isinstance(resp.json(), list), path

        materials = client.get("/api/dashboard/materials").json()
        assert len(materials) == 1
        assert materials[0]["code"] == "M-PO-1"

    @pytest.mark.no_auth
    def test_api_modal_dataset_requires_authentication(self, client: TestClient):
        assert client.get("/api/dashboard/materials").status_code == 401

    def test_production_page_filters(self, client: TestClient, session: Session):
        start = datetime(2026, 1, 10, 8, 0, tzinfo=UTC)
        _create_order(session, "SIM-ORD-0001", start, Decimal("9000"), False)
        _create_order(session, "SIM-ORD-0002", start, Decimal("9000"), False)
        _create_order(session, "OTHER-0001", start, Decimal("9000"), False)

        resp = client.get("/dashboard/production?order=SIM-ORD&per_page=10")
        assert resp.status_code == 200
        assert "SIM-ORD-0001" in resp.text
        assert "SIM-ORD-0002" in resp.text
        assert "OTHER-0001" not in resp.text
        assert "2 matching orders" in resp.text

    def test_production_page_pagination_preserves_filters(self, client: TestClient, session: Session):
        start = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
        for i in range(5):
            _create_order(session, f"SIM-ORD-{i:04d}", start + timedelta(days=i), Decimal("9000"), False)

        resp = client.get("/dashboard/production?order=SIM-ORD&per_page=2&page=2")
        assert resp.status_code == 200
        assert "Page 2 of 3" in resp.text
        assert "order=SIM-ORD" in resp.text
        assert "SIM-ORD-0002" in resp.text

    def test_production_page_has_clickable_kpi_cards(self, client: TestClient):
        resp = client.get("/dashboard/production")
        assert resp.status_code == 200
        assert 'class="kpi-card clickable"' in resp.text
        assert 'onclick="openMaterials()"' in resp.text
        assert 'onclick="openRecipes()"' in resp.text
        assert 'onclick="openResources()"' in resp.text
        assert 'id="kpi-modal"' in resp.text
        assert "openKpiModal" in resp.text

    def test_quality_page_has_clickable_kpi_cards(self, client: TestClient):
        resp = client.get("/dashboard/quality")
        assert resp.status_code == 200
        assert 'onclick="openNonConformities()"' in resp.text
        assert 'onclick="openPendingInspections()"' in resp.text
