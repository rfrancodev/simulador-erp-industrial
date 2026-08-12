"""Tests for CO REST API endpoints."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import session_dependency
from app.domain.entities import Base, ProductionRecipe, ProductionResource
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


@pytest.fixture
def _setup_order(client: TestClient, session: Session):
    """Creates material, recipe, resource and a production order for CO tests."""
    client.post("/api/production/materials", json={
        "material_code": "MAT-CO1",
        "material_name": "CO Material",
        "material_type": "FINISHED_PRODUCT",
        "base_unit": "L",
        "plant": "P001",
    })
    recipe = ProductionRecipe(recipe_code="REC-CO1", material_id=1, version="1.0")
    session.add(recipe)
    session.flush()
    resource = ProductionResource(resource_code="RES-CO1", resource_name="Filler", work_center="WC-01", resource_type="FILLER")
    session.add(resource)
    session.flush()
    now = datetime.now(UTC)
    client.post("/api/production/orders", json={
        "order_number": "PO-CO1",
        "material_id": 1,
        "recipe_id": 1,
        "planned_quantity": "10000",
        "planned_start": now.isoformat(),
        "planned_end": (now + timedelta(hours=8)).isoformat(),
    })
    session.commit()


class TestCostRecordsApi:
    def test_create_cost_record(self, client: TestClient, _setup_order):
        resp = client.post("/api/costing/records", json={
            "production_order_id": 1,
            "planned_material_cost": "10000",
            "planned_labor_cost": "2000",
            "planned_machine_cost": "5000",
            "planned_energy_cost": "1000",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["production_order_id"] == 1
        assert body["planned_total_cost"] == "18000.00"
        assert body["actual_total_cost"] is None

    def test_create_cost_record_invalid_order(self, client: TestClient):
        resp = client.post("/api/costing/records", json={
            "production_order_id": 999,
            "planned_material_cost": "1000",
        })
        assert resp.status_code == 404

    def test_create_cost_record_duplicate(self, client: TestClient, _setup_order):
        payload = {
            "production_order_id": 1,
            "planned_material_cost": "1000",
        }
        client.post("/api/costing/records", json=payload)
        resp = client.post("/api/costing/records", json=payload)
        assert resp.status_code == 409

    def test_list_cost_records(self, client: TestClient, _setup_order):
        client.post("/api/costing/records", json={
            "production_order_id": 1,
            "planned_material_cost": "1000",
        })
        resp = client.get("/api/costing/records")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["page"] == 1

    def test_get_cost_record(self, client: TestClient, _setup_order):
        client.post("/api/costing/records", json={
            "production_order_id": 1,
            "planned_material_cost": "1000",
        })
        resp = client.get("/api/costing/records/1")
        assert resp.status_code == 200
        assert resp.json()["production_order_id"] == 1

    def test_get_cost_record_not_found(self, client: TestClient):
        resp = client.get("/api/costing/records/999")
        assert resp.status_code == 404

    def test_get_cost_record_by_order(self, client: TestClient, _setup_order):
        client.post("/api/costing/records", json={
            "production_order_id": 1,
            "planned_material_cost": "1000",
        })
        resp = client.get("/api/costing/records/order/1")
        assert resp.status_code == 200
        assert resp.json()["planned_material_cost"] == "1000.00"

    def test_get_cost_record_by_order_not_found(self, client: TestClient, _setup_order):
        resp = client.get("/api/costing/records/order/1")
        assert resp.status_code == 404

    def test_get_cost_record_by_invalid_order(self, client: TestClient):
        resp = client.get("/api/costing/records/order/999")
        assert resp.status_code == 404

    def test_update_actual_costs(self, client: TestClient, _setup_order):
        client.post("/api/costing/records", json={
            "production_order_id": 1,
            "planned_material_cost": "10000",
            "planned_labor_cost": "2000",
            "planned_machine_cost": "5000",
            "planned_energy_cost": "1000",
        })
        resp = client.put("/api/costing/records/1/actual", json={
            "actual_material_cost": "11000",
            "actual_labor_cost": "2100",
            "actual_machine_cost": "5100",
            "actual_energy_cost": "1100",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["actual_total_cost"] == "19300.00"

    def test_update_actual_costs_partial(self, client: TestClient, _setup_order):
        client.post("/api/costing/records", json={
            "production_order_id": 1,
            "planned_material_cost": "10000",
            "planned_labor_cost": "2000",
            "planned_machine_cost": "5000",
            "planned_energy_cost": "1000",
        })
        resp = client.put("/api/costing/records/1/actual", json={
            "actual_material_cost": "11000",
        })
        assert resp.status_code == 200
        assert resp.json()["actual_total_cost"] == "11000.00"

    def test_update_actual_costs_not_found(self, client: TestClient):
        resp = client.put("/api/costing/records/999/actual", json={
            "actual_material_cost": "1",
        })
        assert resp.status_code == 404

    def test_get_summary(self, client: TestClient, _setup_order):
        client.post("/api/costing/records", json={
            "production_order_id": 1,
            "planned_material_cost": "10000",
            "planned_labor_cost": "2000",
            "planned_machine_cost": "5000",
            "planned_energy_cost": "1000",
        })
        resp = client.get("/api/costing/records/1/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["planned_total"] == "18000.00"
        assert body["actual_total"] is None
        assert body["variance"] is None

    def test_get_summary_after_actual(self, client: TestClient, _setup_order):
        client.post("/api/costing/records", json={
            "production_order_id": 1,
            "planned_material_cost": "10000",
            "planned_labor_cost": "2000",
            "planned_machine_cost": "5000",
            "planned_energy_cost": "1000",
        })
        client.put("/api/costing/records/1/actual", json={
            "actual_material_cost": "11000",
            "actual_labor_cost": "2100",
            "actual_machine_cost": "5100",
            "actual_energy_cost": "1100",
        })
        resp = client.get("/api/costing/records/1/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["actual_total"] == "19300.00"
        assert body["variance"] == "1300.00"
        assert body["variance_percent"] is not None

    def test_get_summary_not_found(self, client: TestClient):
        resp = client.get("/api/costing/records/999/summary")
        assert resp.status_code == 404