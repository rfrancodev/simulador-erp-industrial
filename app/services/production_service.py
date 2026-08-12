"""Production service — PP-PI business rules.

Owns the transaction boundary: methods commit on success and roll back on
failure, so multi-entity operations stay atomic (M-05). Database exceptions are
translated into domain errors before propagating to the API layer (L-03).
"""

from __future__ import annotations

from logging import getLogger

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    DuplicateEntityError,
    EntityHasDependenciesError,
    EntityNotFoundError,
    RecipeMaterialMismatchError,
)
from app.domain.entities import (
    Batch,
    Material,
    ProductionOrder,
    ProductionRecipe,
    ProductionResource,
)
from app.domain.production.batch import BatchCreate, ProductionResourceCreate
from app.domain.production.material import MaterialCreate, MaterialUpdate
from app.domain.production.recipe import ProductionOrderCreate, ProductionOrderStatus
from app.repositories.production_repository import (
    BatchRepository,
    MaterialRepository,
    ProductionOrderRepository,
    ProductionRecipeRepository,
    ProductionResourceRepository,
)

logger = getLogger(__name__)


class ProductionService:
    def __init__(self, session: Session):
        self._session = session
        self.materials = MaterialRepository(session)
        self.recipes = ProductionRecipeRepository(session)
        self.orders = ProductionOrderRepository(session)
        self.batches = BatchRepository(session)
        self.resources = ProductionResourceRepository(session)

    # ── Materials ──────────────────────────────────────────────────────

    def list_materials(self, skip: int = 0, limit: int = 100) -> list[Material]:
        return self.materials.list_active(skip, limit)

    def get_material(self, id: int) -> Material:
        material = self.materials.get_by_id(id)
        if material is None:
            raise EntityNotFoundError("Material", id)
        return material

    def create_material(self, data: MaterialCreate) -> Material:
        try:
            material = self.materials.create(data)
            self._session.commit()
            logger.info("Material %s created", material.material_code)
            return material
        except IntegrityError:
            self._session.rollback()
            raise DuplicateEntityError("Material", data.material_code) from None

    def update_material(self, id: int, data: MaterialUpdate) -> Material:
        material = self.materials.update(id, data)
        if material is None:
            raise EntityNotFoundError("Material", id)
        self._session.commit()
        return material

    def delete_material(self, id: int) -> None:
        try:
            deleted = self.materials.delete(id)
            if not deleted:
                raise EntityNotFoundError("Material", id)
            self._session.commit()
        except EntityHasDependenciesError:
            self._session.rollback()
            raise

    # ── Production Orders ──────────────────────────────────────────────

    def list_orders(self, skip: int = 0, limit: int = 100) -> list[ProductionOrder]:
        return self.orders.get_all(skip, limit)

    def get_order(self, id: int) -> ProductionOrder:
        order = self.orders.get_with_material(id)
        if order is None:
            raise EntityNotFoundError("ProductionOrder", id)
        return order

    def get_order_by_number(self, order_number: str) -> ProductionOrder:
        order = self.orders.get_by_number(order_number)
        if order is None:
            raise EntityNotFoundError("ProductionOrder", order_number)
        return order

    def list_orders_by_status(self, status: str, skip: int = 0, limit: int = 100) -> list[ProductionOrder]:
        return self.orders.get_by_status(status, skip, limit)

    def create_production_order(self, data: ProductionOrderCreate) -> ProductionOrder:
        material = self.materials.get_by_id(data.material_id)
        if material is None or not material.is_active:
            raise EntityNotFoundError("Material", data.material_id)

        recipe = self.recipes.get_by_id(data.recipe_id)
        if recipe is None:
            raise EntityNotFoundError("ProductionRecipe", data.recipe_id)
        if recipe.material_id != data.material_id:
            raise RecipeMaterialMismatchError(
                recipe_id=data.recipe_id,
                recipe_material_id=recipe.material_id,
                order_material_id=data.material_id,
            )

        order = ProductionOrder(
            order_number=data.order_number,
            material_id=data.material_id,
            recipe_id=data.recipe_id,
            planned_quantity=data.planned_quantity,
            planned_start=data.planned_start,
            planned_end=data.planned_end,
            status=ProductionOrderStatus.CREATED.value,
        )
        try:
            created = self.orders.add(order)
            self._session.commit()
            logger.info("Production order %s created", created.order_number)
            return created
        except IntegrityError:
            self._session.rollback()
            raise DuplicateEntityError("ProductionOrder", data.order_number) from None

    # ── Batches ────────────────────────────────────────────────────────

    def list_batches_by_order(self, order_id: int) -> list[Batch]:
        if self.orders.get_by_id(order_id) is None:
            raise EntityNotFoundError("ProductionOrder", order_id)
        return self.batches.get_by_order(order_id)

    def get_batch_by_number(self, batch_number: str) -> Batch:
        batch = self.batches.get_by_number(batch_number)
        if batch is None:
            raise EntityNotFoundError("Batch", batch_number)
        return batch

    def create_batch(self, data: BatchCreate) -> Batch:
        if self.orders.get_by_id(data.production_order_id) is None:
            raise EntityNotFoundError("ProductionOrder", data.production_order_id)
        if self.resources.get_by_id(data.resource_id) is None:
            raise EntityNotFoundError("ProductionResource", data.resource_id)

        batch = Batch(
            batch_number=data.batch_number,
            production_order_id=data.production_order_id,
            resource_id=data.resource_id,
            planned_quantity=data.planned_quantity,
            status="CREATED",
        )
        try:
            created = self.batches.add(batch)
            self._session.commit()
            logger.info("Batch %s created", created.batch_number)
            return created
        except IntegrityError:
            self._session.rollback()
            raise DuplicateEntityError("Batch", data.batch_number) from None

    # ── Production Resources ───────────────────────────────────────────

    def list_resources(self, skip: int = 0, limit: int = 100) -> list[ProductionResource]:
        return self.resources.get_all(skip, limit)

    def get_resource(self, id: int) -> ProductionResource:
        resource = self.resources.get_by_id(id)
        if resource is None:
            raise EntityNotFoundError("ProductionResource", id)
        return resource

    def get_resource_by_code(self, code: str) -> ProductionResource:
        resource = self.resources.get_by_code(code)
        if resource is None:
            raise EntityNotFoundError("ProductionResource", code)
        return resource

    def list_resources_by_work_center(self, work_center: str) -> list[ProductionResource]:
        return self.resources.get_by_work_center(work_center)

    def create_resource(self, data: ProductionResourceCreate) -> ProductionResource:
        resource = ProductionResource(
            resource_code=data.resource_code,
            resource_name=data.resource_name,
            work_center=data.work_center,
            resource_type=data.resource_type,
        )
        try:
            created = self.resources.add(resource)
            self._session.commit()
            logger.info("Resource %s created", created.resource_code)
            return created
        except IntegrityError:
            self._session.rollback()
            raise DuplicateEntityError("ProductionResource", data.resource_code) from None

    # ── Production Recipes ─────────────────────────────────────────────

    def list_recipes(self, skip: int = 0, limit: int = 100) -> list[ProductionRecipe]:
        return self.recipes.get_all(skip, limit)

    def get_recipe(self, id: int) -> ProductionRecipe:
        recipe = self.recipes.get_by_id(id)
        if recipe is None:
            raise EntityNotFoundError("ProductionRecipe", id)
        return recipe

    def get_recipe_by_code(self, code: str) -> ProductionRecipe:
        recipe = self.recipes.get_by_code(code)
        if recipe is None:
            raise EntityNotFoundError("ProductionRecipe", code)
        return recipe

    def list_active_recipes_for_material(self, material_id: int) -> list[ProductionRecipe]:
        return self.recipes.get_active_for_material(material_id)
