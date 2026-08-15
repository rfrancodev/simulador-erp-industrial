"""Unit tests for AnalyticsService and Dashboard API endpoints."""

from datetime import UTC, datetime, timedelta
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


def _create_order(session, order_number, planned_start, actual_quantity, has_inspection):
    """Create a full order (material/recipe/resource/order/batch + optional inspection + cost)."""
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
        planned_quantity=Decimal("10000"),
        planned_start=planned_start,
        planned_end=planned_start + timedelta(hours=8),
        status="COMPLETED",
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
    session.add(
        CostRecord(
            production_order_id=order.id,
            planned_material_cost=Decimal("100"),
            planned_labor_cost=Decimal("50"),
            planned_machine_cost=Decimal("30"),
            planned_energy_cost=Decimal("20"),
            planned_total_cost=Decimal("200"),
            actual_material_cost=Decimal("110"),
            actual_labor_cost=Decimal("50"),
            actual_machine_cost=Decimal("30"),
            actual_energy_cost=Decimal("20"),
            actual_total_cost=Decimal("210"),
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

    def test_production_stats_empty(self, session: Session):
        svc = AnalyticsService(session)
        stats = svc.production_stats()
        assert stats["materials_count"] == 0
        assert stats["recipes_count"] == 0
        assert stats["resources_count"] == 0
        assert stats["recent_orders"] == []

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
