"""Tests for PP-PI REST API endpoints."""

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


# ── Materials ────────────────────────────────────────────────────────────────

class TestMaterialsApi:
    def test_create_material(self, client: TestClient):
        resp = client.post("/api/production/materials", json={
            "material_code": "MAT-000001",
            "material_name": "Beer 600ml",
            "material_type": "FINISHED_PRODUCT",
            "base_unit": "L",
            "plant": "P001",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["material_code"] == "MAT-000001"
        assert body["id"] == 1

    def test_create_duplicate_material_fails(self, client: TestClient):
        payload = {
            "material_code": "MAT-DUP",
            "material_name": "Test",
            "material_type": "RAW_MATERIAL",
            "base_unit": "KG",
            "plant": "P001",
        }
        client.post("/api/production/materials", json=payload)
        resp = client.post("/api/production/materials", json=payload)
        assert resp.status_code == 409

    def test_list_materials(self, client: TestClient):
        for i in range(3):
            client.post("/api/production/materials", json={
                "material_code": f"MAT-{i:06d}",
                "material_name": f"Material {i}",
                "material_type": "RAW_MATERIAL",
                "base_unit": "KG",
                "plant": "P001",
            })
        resp = client.get("/api/production/materials")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3

    def test_get_material(self, client: TestClient):
        client.post("/api/production/materials", json={
            "material_code": "MAT-GET",
            "material_name": "Get Me",
            "material_type": "FINISHED_PRODUCT",
            "base_unit": "L",
            "plant": "P001",
        })
        resp = client.get("/api/production/materials/1")
        assert resp.status_code == 200
        assert resp.json()["material_code"] == "MAT-GET"

    def test_get_material_not_found(self, client: TestClient):
        resp = client.get("/api/production/materials/999")
        assert resp.status_code == 404

    def test_update_material(self, client: TestClient):
        client.post("/api/production/materials", json={
            "material_code": "MAT-UPD",
            "material_name": "Old Name",
            "material_type": "RAW_MATERIAL",
            "base_unit": "KG",
            "plant": "P001",
        })
        resp = client.put("/api/production/materials/1", json={
            "material_name": "Updated Name",
            "is_active": False,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["material_name"] == "Updated Name"
        assert body["is_active"] is False

    def test_update_material_not_found(self, client: TestClient):
        resp = client.put("/api/production/materials/999", json={"material_name": "X"})
        assert resp.status_code == 404

    def test_delete_material(self, client: TestClient):
        client.post("/api/production/materials", json={
            "material_code": "MAT-DEL",
            "material_name": "Delete Me",
            "material_type": "RAW_MATERIAL",
            "base_unit": "KG",
            "plant": "P001",
        })
        resp = client.delete("/api/production/materials/1")
        assert resp.status_code == 204
        resp2 = client.get("/api/production/materials/1")
        assert resp2.status_code == 404

    def test_delete_material_not_found(self, client: TestClient):
        resp = client.delete("/api/production/materials/999")
        assert resp.status_code == 404


# ── Production Orders ────────────────────────────────────────────────────────

class TestProductionOrdersApi:
    @pytest.fixture(autouse=True)
    def _setup(self, client: TestClient, session: Session):
        client.post("/api/production/materials", json={
            "material_code": "MAT-ORD",
            "material_name": "Order Material",
            "material_type": "FINISHED_PRODUCT",
            "base_unit": "L",
            "plant": "P001",
        })
        recipe = ProductionRecipe(recipe_code="REC-001", material_id=1, version="1.0")
        session.add(recipe)
        session.commit()

    def test_create_order(self, client: TestClient, session: Session):
        now = datetime.now(UTC)
        resp = client.post("/api/production/orders", json={
            "order_number": "PO-000001",
            "material_id": 1,
            "recipe_id": 1,
            "planned_quantity": "10000",
            "planned_start": now.isoformat(),
            "planned_end": (now + timedelta(hours=8)).isoformat(),
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "CREATED"

    def test_create_order_missing_material(self, client: TestClient):
        now = datetime.now(UTC)
        resp = client.post("/api/production/orders", json={
            "order_number": "PO-000002",
            "material_id": 999,
            "recipe_id": 1,
            "planned_quantity": "10000",
            "planned_start": now.isoformat(),
            "planned_end": (now + timedelta(hours=8)).isoformat(),
        })
        assert resp.status_code == 404

    def test_create_order_invalid_dates(self, client: TestClient):
        now = datetime.now(UTC)
        resp = client.post("/api/production/orders", json={
            "order_number": "PO-000003",
            "material_id": 1,
            "recipe_id": 1,
            "planned_quantity": "10000",
            "planned_start": (now + timedelta(hours=8)).isoformat(),
            "planned_end": now.isoformat(),
        })
        assert resp.status_code == 422

    def test_list_orders(self, client: TestClient, session: Session):
        now = datetime.now(UTC)
        client.post("/api/production/orders", json={
            "order_number": "PO-LIST",
            "material_id": 1,
            "recipe_id": 1,
            "planned_quantity": "1000",
            "planned_start": now.isoformat(),
            "planned_end": (now + timedelta(hours=8)).isoformat(),
        })
        resp = client.get("/api/production/orders")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_order_by_number(self, client: TestClient):
        now = datetime.now(UTC)
        client.post("/api/production/orders", json={
            "order_number": "PO-BY-NUM",
            "material_id": 1,
            "recipe_id": 1,
            "planned_quantity": "1000",
            "planned_start": now.isoformat(),
            "planned_end": (now + timedelta(hours=8)).isoformat(),
        })
        resp = client.get("/api/production/orders/number/PO-BY-NUM")
        assert resp.status_code == 200
        assert resp.json()["order_number"] == "PO-BY-NUM"

    def test_get_order_not_found(self, client: TestClient):
        resp = client.get("/api/production/orders/999")
        assert resp.status_code == 404

    def test_get_order_by_number_not_found(self, client: TestClient):
        resp = client.get("/api/production/orders/number/NONEXISTENT")
        assert resp.status_code == 404

    def test_list_orders_by_status(self, client: TestClient):
        now = datetime.now(UTC)
        client.post("/api/production/orders", json={
            "order_number": "PO-STATUS",
            "material_id": 1,
            "recipe_id": 1,
            "planned_quantity": "1000",
            "planned_start": now.isoformat(),
            "planned_end": (now + timedelta(hours=8)).isoformat(),
        })
        resp = client.get("/api/production/orders/status/CREATED")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        resp_empty = client.get("/api/production/orders/status/CLOSED")
        assert resp.status_code == 200
        assert len(resp_empty.json()) == 0


# ── Batches ──────────────────────────────────────────────────────────────────

class TestBatchesApi:
    @pytest.fixture(autouse=True)
    def _setup(self, client: TestClient, session: Session):
        client.post("/api/production/materials", json={
            "material_code": "MAT-BATCH",
            "material_name": "Batch Material",
            "material_type": "FINISHED_PRODUCT",
            "base_unit": "L",
            "plant": "P001",
        })
        recipe = ProductionRecipe(recipe_code="REC-BAT", material_id=1, version="1.0")
        session.add(recipe)
        session.flush()
        resource = ProductionResource(resource_code="RES-001", resource_name="Filler", work_center="WC-01", resource_type="FILLER")
        session.add(resource)
        session.flush()
        now = datetime.now(UTC)
        order = {"order_number": "PO-BATCH", "material_id": 1, "recipe_id": 1,
                 "planned_quantity": "1000", "planned_start": now.isoformat(),
                 "planned_end": (now + timedelta(hours=8)).isoformat()}
        client.post("/api/production/orders", json=order)
        session.commit()

    def test_create_batch(self, client: TestClient):
        resp = client.post("/api/production/batches", json={
            "batch_number": "B-000001",
            "production_order_id": 1,
            "resource_id": 1,
            "planned_quantity": "1000",
        })
        assert resp.status_code == 201
        assert resp.json()["batch_number"] == "B-000001"

    def test_create_batch_duplicate(self, client: TestClient):
        payload = {
            "batch_number": "B-DUP",
            "production_order_id": 1,
            "resource_id": 1,
            "planned_quantity": "1000",
        }
        client.post("/api/production/batches", json=payload)
        resp = client.post("/api/production/batches", json=payload)
        assert resp.status_code == 409

    def test_create_batch_invalid_order(self, client: TestClient):
        resp = client.post("/api/production/batches", json={
            "batch_number": "B-BAD",
            "production_order_id": 999,
            "resource_id": 1,
            "planned_quantity": "1000",
        })
        assert resp.status_code == 404

    def test_list_batches_by_order(self, client: TestClient):
        client.post("/api/production/batches", json={
            "batch_number": "B-LIST",
            "production_order_id": 1,
            "resource_id": 1,
            "planned_quantity": "1000",
        })
        resp = client.get("/api/production/batches/order/1")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_batch_by_number(self, client: TestClient):
        client.post("/api/production/batches", json={
            "batch_number": "B-BY-NUM",
            "production_order_id": 1,
            "resource_id": 1,
            "planned_quantity": "1000",
        })
        resp = client.get("/api/production/batches/number/B-BY-NUM")
        assert resp.status_code == 200
        assert resp.json()["batch_number"] == "B-BY-NUM"

    def test_get_batch_not_found(self, client: TestClient):
        resp = client.get("/api/production/batches/number/NOBATCH")
        assert resp.status_code == 404


# ── Resources ────────────────────────────────────────────────────────────────

class TestResourcesApi:
    def test_create_resource(self, client: TestClient):
        resp = client.post("/api/production/resources", json={
            "resource_code": "FIL-01",
            "resource_name": "Filler Line 1",
            "work_center": "WC-001",
            "resource_type": "FILLER",
        })
        assert resp.status_code == 201
        assert resp.json()["resource_code"] == "FIL-01"

    def test_create_resource_duplicate(self, client: TestClient):
        payload = {"resource_code": "DUP-001", "resource_name": "X", "work_center": "WC-01", "resource_type": "MIXER"}
        client.post("/api/production/resources", json=payload)
        resp = client.post("/api/production/resources", json=payload)
        assert resp.status_code == 409

    def test_list_resources(self, client: TestClient):
        for i in range(3):
            client.post("/api/production/resources", json={
                "resource_code": f"RES-{i:03d}",
                "resource_name": f"Resource {i}",
                "work_center": "WC-001",
                "resource_type": "FILLER",
            })
        resp = client.get("/api/production/resources")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_get_resource(self, client: TestClient):
        client.post("/api/production/resources", json={
            "resource_code": "GET-RES",
            "resource_name": "Get Resource",
            "work_center": "WC-001",
            "resource_type": "FILLER",
        })
        resp = client.get("/api/production/resources/1")
        assert resp.status_code == 200
        assert resp.json()["resource_code"] == "GET-RES"

    def test_get_resource_not_found(self, client: TestClient):
        resp = client.get("/api/production/resources/999")
        assert resp.status_code == 404

    def test_get_resource_by_code(self, client: TestClient):
        client.post("/api/production/resources", json={
            "resource_code": "CODE-RES",
            "resource_name": "By Code",
            "work_center": "WC-001",
            "resource_type": "FILLER",
        })
        resp = client.get("/api/production/resources/code/CODE-RES")
        assert resp.status_code == 200
        assert resp.json()["resource_code"] == "CODE-RES"

    def test_get_resource_by_code_not_found(self, client: TestClient):
        resp = client.get("/api/production/resources/code/NOPE")
        assert resp.status_code == 404

    def test_list_resources_by_work_center(self, client: TestClient):
        client.post("/api/production/resources", json={
            "resource_code": "WC-1-A", "resource_name": "A", "work_center": "WC-001", "resource_type": "FILLER",
        })
        client.post("/api/production/resources", json={
            "resource_code": "WC-1-B", "resource_name": "B", "work_center": "WC-001", "resource_type": "MIXER",
        })
        client.post("/api/production/resources", json={
            "resource_code": "WC-2-A", "resource_name": "C", "work_center": "WC-002", "resource_type": "PACKER",
        })
        resp = client.get("/api/production/resources/work-center/WC-001")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


# ── Recipes ──────────────────────────────────────────────────────────────────

class TestRecipesApi:
    @pytest.fixture(autouse=True)
    def _setup(self, session: Session, client: TestClient):
        client.post("/api/production/materials", json={
            "material_code": "MAT-REC",
            "material_name": "Recipe Material",
            "material_type": "FINISHED_PRODUCT",
            "base_unit": "L",
            "plant": "P001",
        })
        recipe = ProductionRecipe(recipe_code="REC-API-01", material_id=1, version="1.0")
        session.add(recipe)
        session.commit()

    def test_list_recipes(self, client: TestClient):
        resp = client.get("/api/production/recipes")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_recipe_by_code(self, client: TestClient):
        resp = client.get("/api/production/recipes/code/REC-API-01")
        assert resp.status_code == 200
        assert resp.json()["recipe_code"] == "REC-API-01"

    def test_get_recipe_by_code_not_found(self, client: TestClient):
        resp = client.get("/api/production/recipes/code/NOPE")
        assert resp.status_code == 404

    def test_get_recipe_not_found(self, client: TestClient):
        resp = client.get("/api/production/recipes/999")
        assert resp.status_code == 404


# ── Health Check ─────────────────────────────────────────────────────────────

def test_health(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
