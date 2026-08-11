"""Unit tests for PP-PI — Batch and ProductionResource repositories."""

from decimal import Decimal

from app.domain.entities import Batch
from app.repositories.production_repository import (
    BatchRepository,
    ProductionResourceRepository,
)


class TestBatchRepository:
    def test_get_by_number(self, session, sample_batch):
        repo = BatchRepository(session)
        found = repo.get_by_number("B20260810-001")
        assert found is not None
        assert found.id == sample_batch.id

    def test_get_by_number_not_found(self, session):
        repo = BatchRepository(session)
        assert repo.get_by_number("NONEXISTENT") is None

    def test_get_by_order(self, session, sample_batch, sample_production_order):
        repo = BatchRepository(session)
        batches = repo.get_by_order(sample_production_order.id)
        assert len(batches) == 1
        assert batches[0].batch_number == "B20260810-001"

    def test_create_batch(self, session, sample_production_order, sample_resource):
        repo = BatchRepository(session)
        batch = repo.add(
            Batch(
                batch_number="B20260811-002",
                production_order_id=sample_production_order.id,
                resource_id=sample_resource.id,
                planned_quantity=Decimal("5000"),
                status="CREATED",
            )
        )
        assert batch.id is not None
        assert batch.planned_quantity == Decimal("5000")


class TestProductionResourceRepository:
    def test_get_by_code(self, session, sample_resource):
        repo = ProductionResourceRepository(session)
        found = repo.get_by_code("FILLER-04")
        assert found is not None
        assert found.id == sample_resource.id

    def test_get_by_work_center(self, session, sample_resource):
        repo = ProductionResourceRepository(session)
        resources = repo.get_by_work_center("WC-001")
        assert len(resources) == 1
        assert resources[0].resource_code == "FILLER-04"