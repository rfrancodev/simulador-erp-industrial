"""Tests for ProductionRecipe CRUD via REST API (H-02)."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

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


@pytest.fixture
def _setup_materials(client: TestClient):
    """FINISHED_PRODUCT (base_unit L) and RAW_MATERIAL (base_unit KG)."""
    client.post("/api/production/materials", json={
        "material_code": "MAT-FIN",
        "material_name": "Finished Beer",
        "material_type": "FINISHED_PRODUCT",
        "base_unit": "L",
        "plant": "P001",
    })
    client.post("/api/production/materials", json={
        "material_code": "MAT-RAW",
        "material_name": "Raw Malt",
        "material_type": "RAW_MATERIAL",
        "base_unit": "KG",
        "plant": "P001",
    })


_RECIPE_PAYLOAD = {
    "recipe_code": "REC-001",
    "material_id": 1,
    "version": "1.0",
    "components": [
        {"component_material_id": 2, "quantity": "0.02", "unit": "KG"},
    ],
    "operations": [
        {"sequence": 1, "work_center": "WC-001", "operation_description": "Mixing", "standard_time_minutes": 30},
    ],
}


class TestRecipesCrudApi:
    def test_create_recipe(self, client: TestClient, _setup_materials):
        resp = client.post("/api/production/recipes", json=_RECIPE_PAYLOAD)
        assert resp.status_code == 201
        body = resp.json()
        assert body["recipe_code"] == "REC-001"
        assert body["is_active"] is True
        assert len(body["components"]) == 1
        assert len(body["operations"]) == 1

    def test_create_recipe_duplicate_code(self, client: TestClient, _setup_materials):
        client.post("/api/production/recipes", json=_RECIPE_PAYLOAD)
        resp = client.post("/api/production/recipes", json=_RECIPE_PAYLOAD)
        assert resp.status_code == 409

    def test_create_recipe_missing_material(self, client: TestClient, _setup_materials):
        payload = {**_RECIPE_PAYLOAD, "material_id": 999}
        resp = client.post("/api/production/recipes", json=payload)
        assert resp.status_code == 404

    def test_create_recipe_inactive_material(self, client: TestClient, _setup_materials):
        client.put("/api/production/materials/1", json={"is_active": False})
        resp = client.post("/api/production/recipes", json=_RECIPE_PAYLOAD)
        assert resp.status_code == 404

    def test_create_recipe_unit_mismatch(self, client: TestClient, _setup_materials):
        payload = {
            **_RECIPE_PAYLOAD,
            "components": [{"component_material_id": 2, "quantity": "0.02", "unit": "L"}],
        }
        resp = client.post("/api/production/recipes", json=payload)
        assert resp.status_code == 422
        assert "does not match" in resp.json()["detail"]

    def test_create_recipe_missing_component_material(self, client: TestClient, _setup_materials):
        payload = {
            **_RECIPE_PAYLOAD,
            "components": [{"component_material_id": 999, "quantity": "0.02", "unit": "KG"}],
        }
        resp = client.post("/api/production/recipes", json=payload)
        assert resp.status_code == 404

    def test_get_recipe_includes_bom(self, client: TestClient, _setup_materials):
        client.post("/api/production/recipes", json=_RECIPE_PAYLOAD)
        resp = client.get("/api/production/recipes/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["components"][0]["component_material_id"] == 2
        assert body["operations"][0]["operation_description"] == "Mixing"

    def test_update_recipe_basic_fields(self, client: TestClient, _setup_materials):
        client.post("/api/production/recipes", json=_RECIPE_PAYLOAD)
        resp = client.put("/api/production/recipes/1", json={"version": "2.0"})
        assert resp.status_code == 200
        assert resp.json()["version"] == "2.0"

    def test_update_recipe_not_found(self, client: TestClient, _setup_materials):
        resp = client.put("/api/production/recipes/999", json={"version": "2.0"})
        assert resp.status_code == 404

    def test_update_recipe_replace_components(self, client: TestClient, _setup_materials):
        client.post("/api/production/recipes", json=_RECIPE_PAYLOAD)
        resp = client.put("/api/production/recipes/1", json={
            "components": [{"component_material_id": 2, "quantity": "0.03", "unit": "KG"}],
        })
        assert resp.status_code == 200
        assert resp.json()["components"][0]["quantity"] == "0.030"

    def test_delete_recipe(self, client: TestClient, _setup_materials):
        client.post("/api/production/recipes", json=_RECIPE_PAYLOAD)
        resp = client.delete("/api/production/recipes/1")
        assert resp.status_code == 204
        resp2 = client.get("/api/production/recipes/1")
        assert resp2.status_code == 404

    def test_delete_recipe_not_found(self, client: TestClient, _setup_materials):
        resp = client.delete("/api/production/recipes/999")
        assert resp.status_code == 404

    def test_delete_recipe_with_dependency(self, client: TestClient, _setup_materials):
        client.post("/api/production/recipes", json=_RECIPE_PAYLOAD)
        now = datetime.now(UTC)
        resp_order = client.post("/api/production/orders", json={
            "order_number": "PO-REC-DEP",
            "material_id": 1,
            "recipe_id": 1,
            "planned_quantity": "1000",
            "planned_start": now.isoformat(),
            "planned_end": (now + timedelta(hours=8)).isoformat(),
        })
        assert resp_order.status_code == 201
        resp = client.delete("/api/production/recipes/1")
        assert resp.status_code == 409
        assert "production_orders" in resp.json()["detail"]

    def test_list_recipes_paginated(self, client: TestClient, _setup_materials):
        client.post("/api/production/recipes", json=_RECIPE_PAYLOAD)
        resp = client.get("/api/production/recipes")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert len(resp.json()["items"]) == 1

    def test_get_order_includes_recipe(self, client: TestClient, _setup_materials):
        client.post("/api/production/recipes", json=_RECIPE_PAYLOAD)
        now = datetime.now(UTC)
        client.post("/api/production/orders", json={
            "order_number": "PO-REC-CARGA",
            "material_id": 1,
            "recipe_id": 1,
            "planned_quantity": "1000",
            "planned_start": now.isoformat(),
            "planned_end": (now + timedelta(hours=8)).isoformat(),
        })
        resp = client.get("/api/production/orders/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["recipe"]["recipe_code"] == "REC-001"