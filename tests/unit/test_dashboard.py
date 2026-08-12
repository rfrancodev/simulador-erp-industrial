"""Unit tests for AnalyticsService and Dashboard API endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.analytics.service import AnalyticsService
from app.database.connection import session_dependency
from app.domain.entities import Base
from app.main import app


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


class TestDashboardAPI:
    def test_home_page_renders(self, client: TestClient):
        resp = client.get("/dashboard/")
        assert resp.status_code == 200
        assert "Dashboard Executivo" in resp.text
        assert "Industrial ERP Simulator" in resp.text

    def test_order_360_page_renders(self, client: TestClient):
        resp = client.get("/dashboard/order-360")
        assert resp.status_code == 200
        assert "Order 360" in resp.text

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
