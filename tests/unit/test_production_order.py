"""Unit tests for Production Order domain model and repository."""

from decimal import Decimal

import pytest

from app.domain.entities import ProductionOrder
from app.domain.production.recipe import ProductionOrderCreate, ProductionOrderStatus
from app.repositories.production_repository import ProductionOrderRepository


class TestProductionOrderModel:
    def test_order_creation(self, session, sample_production_order):
        assert sample_production_order.id is not None
        assert sample_production_order.order_number == "PO-2026-000001"
        assert sample_production_order.planned_quantity == Decimal("10000")
        assert sample_production_order.status == "CREATED"

    def test_order_status_enum(self):
        assert ProductionOrderStatus.CREATED.value == "CREATED"
        assert ProductionOrderStatus.COMPLETED.value == "COMPLETED"


class TestProductionOrderRepository:
    def test_get_by_number(self, session, sample_production_order):
        repo = ProductionOrderRepository(session)
        found = repo.get_by_number("PO-2026-000001")
        assert found is not None
        assert found.id == sample_production_order.id

    def test_get_by_number_not_found(self, session):
        repo = ProductionOrderRepository(session)
        found = repo.get_by_number("PO-NONEXISTENT")
        assert found is None

    def test_get_by_status(self, session, sample_production_order):
        repo = ProductionOrderRepository(session)
        orders = repo.get_by_status("CREATED")
        assert len(orders) == 1
        assert orders[0].order_number == "PO-2026-000001"

    def test_get_with_material(self, session, sample_production_order):
        repo = ProductionOrderRepository(session)
        order = repo.get_with_material(sample_production_order.id)
        assert order is not None
        assert order.material.material_code == "MAT-BEER-600"
