"""Tests for Production Confirmation and Material Consumption API (TASK-015)."""

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
def _setup_batch(client: TestClient, session: Session):
    """Creates a finished product + raw material + recipe + resource + order + batch."""
    client.post("/api/production/materials", json={
        "material_code": "MAT-FIN",
        "material_name": "Finished Product",
        "material_type": "FINISHED_PRODUCT",
        "base_unit": "L",
        "plant": "P001",
    })
    client.post("/api/production/materials", json={
        "material_code": "MAT-RAW",
        "material_name": "Raw Material",
        "material_type": "RAW_MATERIAL",
        "base_unit": "KG",
        "plant": "P001",
    })
    recipe = ProductionRecipe(recipe_code="REC-1", material_id=1, version="1.0")
    session.add(recipe)
    session.flush()
    resource = ProductionResource(resource_code="RES-1", resource_name="Filler", work_center="WC-01", resource_type="FILLER")
    session.add(resource)
    session.flush()
    now = datetime.now(UTC)
    client.post("/api/production/orders", json={
        "order_number": "PO-1",
        "material_id": 1,
        "recipe_id": 1,
        "planned_quantity": "1000",
        "planned_start": now.isoformat(),
        "planned_end": (now + timedelta(hours=8)).isoformat(),
    })
    client.post("/api/production/batches", json={
        "batch_number": "B-1",
        "production_order_id": 1,
        "resource_id": 1,
        "planned_quantity": "1000",
    })
    session.commit()


class TestProductionConfirmationApi:
    def test_create_confirmation(self, client: TestClient, _setup_batch):
        now = datetime.now(UTC)
        resp = client.post("/api/production/confirmations", json={
            "batch_id": 1,
            "operation": "Mashing",
            "quantity": "1000",
            "unit": "L",
            "confirmation_time": now.isoformat(),
            "is_final": True,
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["operation"] == "Mashing"
        assert body["is_final"] is True

    def test_list_confirmations_by_batch(self, client: TestClient, _setup_batch):
        now = datetime.now(UTC)
        client.post("/api/production/confirmations", json={
            "batch_id": 1,
            "operation": "Filling",
            "quantity": "1000",
            "unit": "L",
            "confirmation_time": now.isoformat(),
        })
        resp = client.get("/api/production/batches/1/confirmations")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert len(resp.json()["items"]) == 1

    def test_create_confirmation_invalid_batch(self, client: TestClient):
        now = datetime.now(UTC)
        resp = client.post("/api/production/confirmations", json={
            "batch_id": 999,
            "operation": "Mashing",
            "quantity": "1000",
            "unit": "L",
            "confirmation_time": now.isoformat(),
        })
        assert resp.status_code == 404


class TestMaterialConsumptionApi:
    def test_create_consumption(self, client: TestClient, _setup_batch):
        now = datetime.now(UTC)
        resp = client.post("/api/production/consumptions", json={
            "batch_id": 1,
            "material_id": 2,
            "quantity": "50",
            "unit": "KG",
            "consumption_time": now.isoformat(),
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["quantity"] == "50.000"
        assert body["unit"] == "KG"

    def test_list_consumptions_by_batch(self, client: TestClient, _setup_batch):
        now = datetime.now(UTC)
        client.post("/api/production/consumptions", json={
            "batch_id": 1,
            "material_id": 2,
            "quantity": "50",
            "unit": "KG",
            "consumption_time": now.isoformat(),
        })
        resp = client.get("/api/production/batches/1/consumptions")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert len(resp.json()["items"]) == 1

    def test_create_consumption_unit_mismatch(self, client: TestClient, _setup_batch):
        now = datetime.now(UTC)
        resp = client.post("/api/production/consumptions", json={
            "batch_id": 1,
            "material_id": 2,
            "quantity": "50",
            "unit": "L",  # material 2 base_unit is KG
            "consumption_time": now.isoformat(),
        })
        assert resp.status_code == 422

    def test_create_consumption_invalid_material(self, client: TestClient, _setup_batch):
        now = datetime.now(UTC)
        resp = client.post("/api/production/consumptions", json={
            "batch_id": 1,
            "material_id": 999,
            "quantity": "50",
            "unit": "KG",
            "consumption_time": now.isoformat(),
        })
        assert resp.status_code == 404

    def test_create_consumption_invalid_batch(self, client: TestClient):
        now = datetime.now(UTC)
        resp = client.post("/api/production/consumptions", json={
            "batch_id": 999,
            "material_id": 1,
            "quantity": "50",
            "unit": "KG",
            "consumption_time": now.isoformat(),
        })
        assert resp.status_code == 404
