"""Tests for QM REST API endpoints."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

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
def _setup_batch(client: TestClient, session: Session):
    """Creates a material, recipe, resource, order and batch for inspection tests."""
    client.post("/api/production/materials", json={
        "material_code": "MAT-QM1",
        "material_name": "QM Material",
        "material_type": "FINISHED_PRODUCT",
        "base_unit": "L",
        "plant": "P001",
    })
    recipe = ProductionRecipe(recipe_code="REC-QM1", material_id=1, version="1.0")
    session.add(recipe)
    session.flush()
    resource = ProductionResource(resource_code="RES-QM1", resource_name="Filler", work_center="WC-01", resource_type="FILLER")
    session.add(resource)
    session.flush()
    now = datetime.now(UTC)
    client.post("/api/production/orders", json={
        "order_number": "PO-QM1",
        "material_id": 1,
        "recipe_id": 1,
        "planned_quantity": "1000",
        "planned_start": now.isoformat(),
        "planned_end": (now + timedelta(hours=8)).isoformat(),
    })
    client.post("/api/production/batches", json={
        "batch_number": "B-QM1",
        "production_order_id": 1,
        "resource_id": 1,
        "planned_quantity": "1000",
    })
    session.commit()


# ── Quality Inspections ──────────────────────────────────────────────────────

class TestInspectionsApi:
    def test_batch_auto_creates_inspection(self, client: TestClient, _setup_batch):
        resp = client.get("/api/quality/inspections/batch/1")
        assert resp.status_code == 200
        assert resp.json()["inspection_status"] == "PENDING"

    def test_create_inspection_invalid_batch(self, client: TestClient):
        resp = client.post("/api/quality/inspections", json={
            "batch_id": 999,
            "inspection_lot": "QI-2026-0002",
        })
        assert resp.status_code == 404

    def test_create_inspection_for_batch_with_existing_inspection(self, client: TestClient, _setup_batch):
        resp = client.post("/api/quality/inspections", json={
            "batch_id": 1,
            "inspection_lot": "QI-DUP",
        })
        assert resp.status_code == 409

    def test_list_inspections(self, client: TestClient, _setup_batch):
        resp = client.get("/api/quality/inspections")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert len(resp.json()["items"]) == 1

    def test_get_inspection(self, client: TestClient, _setup_batch):
        resp = client.get("/api/quality/inspections/1")
        assert resp.status_code == 200
        assert resp.json()["inspection_status"] == "PENDING"

    def test_get_inspection_not_found(self, client: TestClient):
        resp = client.get("/api/quality/inspections/999")
        assert resp.status_code == 404

    def test_get_inspection_by_lot(self, client: TestClient, _setup_batch):
        resp = client.get("/api/quality/inspections/lot/QI-000000000001")
        assert resp.status_code == 200
        assert resp.json()["inspection_status"] == "PENDING"

    def test_get_inspection_by_lot_not_found(self, client: TestClient):
        resp = client.get("/api/quality/inspections/lot/NOPE")
        assert resp.status_code == 404

    def test_get_inspection_by_batch(self, client: TestClient, _setup_batch):
        resp = client.get("/api/quality/inspections/batch/1")
        assert resp.status_code == 200
        assert resp.json()["inspection_status"] == "PENDING"

    def test_get_inspection_by_batch_not_found(self, client: TestClient):
        resp = client.get("/api/quality/inspections/batch/999")
        assert resp.status_code == 404

    def test_update_inspection_result(self, client: TestClient, _setup_batch):
        client.put("/api/quality/inspections/1/result", json={"inspection_status": "IN_PROGRESS"})
        resp = client.put("/api/quality/inspections/1/result", json={
            "inspection_status": "PASSED",
            "pH": "4.21",
            "alcohol_percent": "4.7",
            "temperature": "20.5",
            "inspector_notes": "All parameters within spec",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["inspection_status"] == "PASSED"
        assert body["pH"] == "4.21"
        assert body["alcohol_percent"] == "4.7"

    def test_update_inspection_result_invalid_transition(self, client: TestClient, _setup_batch):
        resp = client.put("/api/quality/inspections/1/result", json={"inspection_status": "PASSED"})
        assert resp.status_code == 409

    def test_update_inspection_result_invalid_status(self, client: TestClient, _setup_batch):
        resp = client.put("/api/quality/inspections/1/result", json={"inspection_status": "INVALID"})
        assert resp.status_code == 422

    def test_update_inspection_result_invalid_ph(self, client: TestClient, _setup_batch):
        resp = client.put("/api/quality/inspections/1/result", json={
            "inspection_status": "PASSED",
            "pH": "20",
        })
        assert resp.status_code == 422

    def test_update_inspection_result_not_found(self, client: TestClient):
        resp = client.put("/api/quality/inspections/999/result", json={"inspection_status": "PASSED"})
        assert resp.status_code == 404

    def test_update_inspection_result_whitelist_protects_identity(self, client: TestClient, _setup_batch):
        client.put("/api/quality/inspections/1/result", json={"inspection_status": "IN_PROGRESS"})
        resp = client.put("/api/quality/inspections/1/result", json={
            "inspection_status": "PASSED",
            "inspection_lot": "HACKED",
        })
        assert resp.status_code == 200
        # identity fields are not mutable via the result endpoint
        assert resp.json()["inspection_lot"] == "QI-000000000001"


# ── Non-Conformities ─────────────────────────────────────────────────────────

class TestNonConformitiesApi:
    def test_add_non_conformity(self, client: TestClient, _setup_batch):
        resp = client.post("/api/quality/inspections/1/non-conformities", json={
            "defect_type": "OFF_SPEC",
            "defect_code": "NC-001",
            "description": "CO2 level below specification",
            "severity": "MAJOR",
            "disposition": "REWORK",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["defect_code"] == "NC-001"
        assert body["severity"] == "MAJOR"
        assert body["disposition"] == "REWORK"

    def test_add_non_conformity_invalid_inspection(self, client: TestClient):
        resp = client.post("/api/quality/inspections/999/non-conformities", json={
            "defect_type": "OFF_SPEC",
            "defect_code": "NC-XXX",
            "description": "Some defect",
            "severity": "MINOR",
            "disposition": "USE_AS_IS",
        })
        assert resp.status_code == 404

    def test_add_non_conformity_invalid_enum(self, client: TestClient, _setup_batch):
        resp = client.post("/api/quality/inspections/1/non-conformities", json={
            "defect_type": "BAD",
            "defect_code": "NC-002",
            "description": "Bad severity",
            "severity": "NONSENSE",
            "disposition": "USE_AS_IS",
        })
        assert resp.status_code == 422

    def test_list_non_conformities(self, client: TestClient, _setup_batch):
        client.post("/api/quality/inspections/1/non-conformities", json={
            "defect_type": "OFF_SPEC",
            "defect_code": "NC-003",
            "description": "Defect A",
            "severity": "MAJOR",
            "disposition": "REWORK",
        })
        client.post("/api/quality/inspections/1/non-conformities", json={
            "defect_type": "OFF_SPEC",
            "defect_code": "NC-004",
            "description": "Defect B",
            "severity": "CRITICAL",
            "disposition": "SCRAP",
        })
        resp = client.get("/api/quality/inspections/1/non-conformities")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2
        assert len(resp.json()["items"]) == 2

    def test_list_non_conformities_empty(self, client: TestClient, _setup_batch):
        resp = client.get("/api/quality/inspections/1/non-conformities")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert len(resp.json()["items"]) == 0