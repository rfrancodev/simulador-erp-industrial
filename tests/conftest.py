"""Pytest configuration and shared fixtures."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.domain.entities import (
    Base,
    Batch,
    Material,
    ProductionOrder,
    ProductionRecipe,
    ProductionResource,
)


@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine) -> Generator[Session, None, None]:
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_material(session: Session) -> Material:
    material = Material(
        material_code="MAT-BEER-600",
        material_name="Beer 600ml",
        material_type="FINISHED_PRODUCT",
        base_unit="L",
        plant="P001",
    )
    session.add(material)
    session.flush()
    return material


@pytest.fixture
def sample_recipe(session: Session, sample_material: Material) -> ProductionRecipe:
    recipe = ProductionRecipe(
        recipe_code="REC-BEER-001",
        material_id=sample_material.id,
        version="1.0",
    )
    session.add(recipe)
    session.flush()
    return recipe


@pytest.fixture
def sample_production_order(
    session: Session, sample_material: Material, sample_recipe: ProductionRecipe
) -> ProductionOrder:
    now = datetime.now(UTC)
    order = ProductionOrder(
        order_number="PO-2026-000001",
        material_id=sample_material.id,
        recipe_id=sample_recipe.id,
        planned_quantity=Decimal("10000"),
        planned_start=now,
        planned_end=now + timedelta(hours=8),
        status="CREATED",
    )
    session.add(order)
    session.flush()
    return order


@pytest.fixture
def sample_resource(session: Session) -> ProductionResource:
    resource = ProductionResource(
        resource_code="FILLER-04",
        resource_name="Filler Line 04",
        work_center="WC-001",
        resource_type="FILLER",
    )
    session.add(resource)
    session.flush()
    return resource


@pytest.fixture
def sample_batch(
    session: Session, sample_production_order: ProductionOrder, sample_resource: ProductionResource
) -> Batch:
    batch = Batch(
        batch_number="B20260810-001",
        production_order_id=sample_production_order.id,
        resource_id=sample_resource.id,
        planned_quantity=Decimal("10000"),
        status="CREATED",
    )
    session.add(batch)
    session.flush()
    return batch