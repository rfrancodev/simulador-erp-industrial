"""Unit tests for ProductionService business rules (H-03, M-05, L-03)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.exceptions import (
    DuplicateEntityError,
    EntityNotFoundError,
    RecipeMaterialMismatchError,
)
from app.domain.production.material import MaterialCreate, MaterialType
from app.domain.production.recipe import ProductionOrderCreate
from app.repositories.production_repository import MaterialRepository, ProductionRecipeRepository
from app.services.production_service import ProductionService


def _order_data(material_id: int, recipe_id: int, order_number: str = "PO-2026-000100"):
    now = datetime.now(UTC)
    return ProductionOrderCreate(
        order_number=order_number,
        material_id=material_id,
        recipe_id=recipe_id,
        planned_quantity=Decimal("10000"),
        planned_start=now,
        planned_end=now + timedelta(hours=8),
    )


class TestCreateProductionOrder:
    def test_create_order_success(self, session, sample_material, sample_recipe):
        service = ProductionService(session)
        order = service.create_production_order(
            _order_data(sample_material.id, sample_recipe.id)
        )
        assert order.id is not None
        assert order.status == "CREATED"

    def test_create_order_material_recipe_mismatch(self, session, sample_material, sample_recipe):
        other = MaterialRepository(session).create(
            MaterialCreate(
                material_code="MAT-STOUT-600",
                material_name="Premium Stout",
                material_type=MaterialType.FINISHED_PRODUCT,
                base_unit="L",
                plant="P001",
            )
        )
        service = ProductionService(session)
        with pytest.raises(RecipeMaterialMismatchError):
            service.create_production_order(_order_data(other.id, sample_recipe.id))

    def test_create_order_recipe_not_found(self, session, sample_material):
        service = ProductionService(session)
        with pytest.raises(EntityNotFoundError):
            service.create_production_order(_order_data(sample_material.id, recipe_id=9999))

    def test_create_order_material_not_found(self, session, sample_recipe):
        service = ProductionService(session)
        with pytest.raises(EntityNotFoundError):
            service.create_production_order(_order_data(material_id=9999, recipe_id=sample_recipe.id))

    def test_create_order_inactive_material_rejected(self, session, sample_material, sample_recipe):
        sample_material.is_active = False
        session.flush()
        service = ProductionService(session)
        with pytest.raises(EntityNotFoundError):
            service.create_production_order(_order_data(sample_material.id, sample_recipe.id))

    def test_create_duplicate_order_number(self, session, sample_material, sample_recipe):
        service = ProductionService(session)
        service.create_production_order(_order_data(sample_material.id, sample_recipe.id, "PO-DUP-0001"))
        with pytest.raises(DuplicateEntityError):
            service.create_production_order(_order_data(sample_material.id, sample_recipe.id, "PO-DUP-0001"))

    def test_create_order_rolls_back_on_failure(self, session, sample_material, sample_recipe):
        service = ProductionService(session)
        service.create_production_order(_order_data(sample_material.id, sample_recipe.id, "PO-RB-0001"))
        with pytest.raises(DuplicateEntityError):
            service.create_production_order(_order_data(sample_material.id, sample_recipe.id, "PO-RB-0001"))
        # Session must remain usable after rollback (no stale transaction).
        count = service.orders.count()
        assert count == 1