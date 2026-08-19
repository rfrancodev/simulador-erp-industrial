"""Production service — PP-PI business rules.

Owns the transaction boundary: methods commit on success and roll back on
failure, so multi-entity operations stay atomic (M-05). Database exceptions are
translated into domain errors before propagating to the API layer (L-03).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from logging import getLogger

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.events import (
    EVENT_BATCH_COMPLETED,
    EVENT_BATCH_CREATED,
    EVENT_ORDER_COMPLETED,
    event_bus,
)
from app.core.exceptions import (
    ComponentUnitMismatchError,
    DatabaseIntegrityError,
    DuplicateEntityError,
    EntityHasDependenciesError,
    EntityNotFoundError,
    RecipeMaterialMismatchError,
)
from app.domain.entities import (
    Batch,
    Material,
    MaterialConsumption,
    ProductionConfirmation,
    ProductionOrder,
    ProductionRecipe,
    ProductionResource,
    RecipeComponent,
    RecipeOperation,
)
from app.domain.production.batch import (
    BatchCreate,
    BatchStatus,
    MaterialConsumptionCreate,
    ProductionConfirmationCreate,
    ProductionResourceCreate,
)
from app.domain.production.material import MaterialCreate, MaterialUpdate
from app.domain.production.recipe import (
    ProductionOrderCreate,
    ProductionOrderStatus,
    ProductionRecipeCreate,
    ProductionRecipeUpdate,
)
from app.domain.state_machine import (
    BATCH_TRANSITIONS,
    PRODUCTION_ORDER_TRANSITIONS,
    validate_transition,
)
from app.repositories.production_repository import (
    BatchRepository,
    MaterialConsumptionRepository,
    MaterialRepository,
    ProductionConfirmationRepository,
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
        self.confirmations = ProductionConfirmationRepository(session)
        self.consumptions = MaterialConsumptionRepository(session)

    # ── Materials ──────────────────────────────────────────────────────

    def list_materials(self, skip: int = 0, limit: int = 100, active: bool | None = True) -> list[Material]:
        if active is True:
            return self.materials.list_active(skip, limit)
        elif active is False:
            return self.materials.list_inactive(skip, limit)
        else:
            return self.materials.list_all(skip, limit)

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
            duplicate = self.materials.get_by_code(data.material_code) is not None
            self._session.rollback()
            if duplicate:
                raise DuplicateEntityError("Material", data.material_code) from None
            raise DatabaseIntegrityError("Material") from None

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

    def list_orders_by_status(self, status: ProductionOrderStatus, skip: int = 0, limit: int = 100) -> list[ProductionOrder]:
        return self.orders.get_by_status(status.value, skip, limit)

    def create_production_order(self, data: ProductionOrderCreate) -> ProductionOrder:
        material = self.materials.get_by_id(data.material_id)
        if material is None or not material.is_active:
            raise EntityNotFoundError("Material", data.material_id)

        recipe_stmt = (
            select(ProductionRecipe)
            .where(ProductionRecipe.id == data.recipe_id)
            .with_for_update()
        )
        recipe = self._session.execute(recipe_stmt).scalar_one_or_none()
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
            duplicate = self.orders.get_by_number(data.order_number) is not None
            self._session.rollback()
            if duplicate:
                raise DuplicateEntityError("ProductionOrder", data.order_number) from None
            raise DatabaseIntegrityError("ProductionOrder") from None

    def update_order_status(self, id: int, status: ProductionOrderStatus) -> ProductionOrder:
        order = self.orders.get_by_id(id)
        if order is None:
            raise EntityNotFoundError("ProductionOrder", id)

        current = ProductionOrderStatus(order.status)
        validate_transition(
            PRODUCTION_ORDER_TRANSITIONS, current, status, entity="ProductionOrder"
        )

        now = datetime.now(UTC)
        if status == ProductionOrderStatus.IN_PROCESS and order.actual_start is None:
            order.actual_start = now
        if status in (ProductionOrderStatus.COMPLETED, ProductionOrderStatus.PARTIAL):
            order.actual_end = now
            batch_actuals = self.batches.sum_actual_by_order(order.id)
            if batch_actuals is not None:
                order.actual_quantity = batch_actuals.quantize(Decimal("0.001"))

        order.status = status.value
        try:
            if status in (ProductionOrderStatus.COMPLETED, ProductionOrderStatus.PARTIAL):
                event_bus.publish(EVENT_ORDER_COMPLETED, session=self._session, order=order)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        logger.info("Production order %s status %s -> %s", order.order_number, current.value, status.value)
        return order

    # ── Batches ────────────────────────────────────────────────────────

    def list_batches_by_order(self, order_id: int, skip: int = 0, limit: int = 100) -> list[Batch]:
        if self.orders.get_by_id(order_id) is None:
            raise EntityNotFoundError("ProductionOrder", order_id)
        return self.batches.get_by_order(order_id, skip, limit)

    def get_batch_by_number(self, batch_number: str) -> Batch:
        batch = self.batches.get_by_number(batch_number)
        if batch is None:
            raise EntityNotFoundError("Batch", batch_number)
        return batch

    def update_batch_status(self, id: int, status: BatchStatus) -> Batch:
        batch = self.batches.get_by_id(id)
        if batch is None:
            raise EntityNotFoundError("Batch", id)

        current = BatchStatus(batch.status)
        validate_transition(BATCH_TRANSITIONS, current, status, entity="Batch")

        if status == BatchStatus.COMPLETED and batch.completed_at is None:
            batch.completed_at = datetime.now(UTC)
        elif status != BatchStatus.COMPLETED:
            batch.completed_at = None

        try:
            updated = self.batches.update_status(id, status)
            if status == BatchStatus.COMPLETED:
                self._consolidate_batch_actuals(updated)
            if status in (BatchStatus.COMPLETED, BatchStatus.SCRAP):
                event_bus.publish(
                    EVENT_BATCH_COMPLETED, session=self._session, batch=updated
                )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        logger.info("Batch %s status %s -> %s", updated.batch_number, current.value, status.value)
        return updated

    def _consolidate_batch_actuals(self, batch: Batch) -> None:
        """Fill ``actual_quantity``/``yield_percent`` of a COMPLETED batch.

        Uses the batch's final production confirmation (``is_final``, most
        recent ``confirmation_time``, highest ``id`` on tie). When no final
        confirmation exists the actuals stay ``None`` — no quantity is guessed.
        Runs inside the same transaction as the status update (M-05).
        """
        confirmation = self.confirmations.get_final_confirmation(batch.id)
        if confirmation is None:
            return
        batch.actual_quantity = confirmation.quantity.quantize(Decimal("0.001"))
        if batch.planned_quantity > 0:
            batch.yield_percent = (
                (batch.actual_quantity / batch.planned_quantity) * 100
            ).quantize(Decimal("0.01"))

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
            status=BatchStatus.CREATED.value,
        )
        try:
            created = self.batches.add(batch)
            event_bus.publish(EVENT_BATCH_CREATED, session=self._session, batch=created)
            self._session.commit()
            logger.info("Batch %s created", created.batch_number)
            return created
        except IntegrityError:
            self._session.rollback()
            duplicate = self.batches.get_by_number(data.batch_number) is not None
            self._session.rollback()
            if duplicate:
                raise DuplicateEntityError("Batch", data.batch_number) from None
            raise DatabaseIntegrityError("Batch") from None
        except Exception:
            self._session.rollback()
            raise

    # ── Production Confirmations ────────────────────────────────────────

    def list_confirmations_by_batch(self, batch_id: int, skip: int = 0, limit: int = 100) -> list[ProductionConfirmation]:
        if self.batches.get_by_id(batch_id) is None:
            raise EntityNotFoundError("Batch", batch_id)
        return self.confirmations.get_by_batch(batch_id, skip, limit)

    def create_confirmation(self, data: ProductionConfirmationCreate) -> ProductionConfirmation:
        if self.batches.get_by_id(data.batch_id) is None:
            raise EntityNotFoundError("Batch", data.batch_id)

        confirmation = ProductionConfirmation(
            batch_id=data.batch_id,
            operation=data.operation,
            quantity=data.quantity,
            unit=data.unit,
            confirmation_time=data.confirmation_time,
            is_final=data.is_final,
            notes=data.notes,
        )
        try:
            created = self.confirmations.add(confirmation)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        logger.info("Production confirmation for batch %s recorded", data.batch_id)
        return created

    # ── Material Consumptions ───────────────────────────────────────────

    def list_consumptions_by_batch(self, batch_id: int, skip: int = 0, limit: int = 100) -> list[MaterialConsumption]:
        if self.batches.get_by_id(batch_id) is None:
            raise EntityNotFoundError("Batch", batch_id)
        return self.consumptions.get_by_batch(batch_id, skip, limit)

    def create_consumption(self, data: MaterialConsumptionCreate) -> MaterialConsumption:
        if self.batches.get_by_id(data.batch_id) is None:
            raise EntityNotFoundError("Batch", data.batch_id)
        material = self.materials.get_by_id(data.material_id)
        if material is None:
            raise EntityNotFoundError("Material", data.material_id)
        if data.unit != material.base_unit:
            raise ComponentUnitMismatchError(data.material_id, data.unit, material.base_unit)

        consumption = MaterialConsumption(
            batch_id=data.batch_id,
            material_id=data.material_id,
            quantity=data.quantity,
            unit=data.unit,
            consumption_time=data.consumption_time,
        )
        try:
            created = self.consumptions.add(consumption)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        logger.info("Material consumption for batch %s recorded", data.batch_id)
        return created

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

    def list_resources_by_work_center(self, work_center: str, skip: int = 0, limit: int = 100) -> list[ProductionResource]:
        return self.resources.get_by_work_center(work_center, skip, limit)

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
            duplicate = self.resources.get_by_code(data.resource_code) is not None
            self._session.rollback()
            if duplicate:
                raise DuplicateEntityError("ProductionResource", data.resource_code) from None
            raise DatabaseIntegrityError("ProductionResource") from None

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

    def list_active_recipes_for_material(self, material_id: int, skip: int = 0, limit: int = 100) -> list[ProductionRecipe]:
        return self.recipes.get_active_for_material(material_id, skip, limit)

    def _validate_component(
        self, material_id: int, unit: str
    ) -> None:
        """Validate a BOM component against the referenced material (M-11/L-05)."""
        component_material = self.materials.get_by_id(material_id)
        if component_material is None:
            raise EntityNotFoundError("Material", material_id)
        if unit != component_material.base_unit:
            raise ComponentUnitMismatchError(material_id, unit, component_material.base_unit)

    def _recipe_with_bom(
        self, recipe: ProductionRecipe, data: ProductionRecipeCreate
    ) -> ProductionRecipe:
        for component in data.components:
            self._validate_component(component.component_material_id, component.unit)
            recipe.components.append(
                RecipeComponent(
                    component_material_id=component.component_material_id,
                    quantity=component.quantity,
                    unit=component.unit,
                )
            )
        for operation in data.operations:
            recipe.operations.append(
                RecipeOperation(
                    sequence=operation.sequence,
                    work_center=operation.work_center,
                    operation_description=operation.operation_description,
                    standard_time_minutes=operation.standard_time_minutes,
                )
            )
        return recipe

    def create_recipe(self, data: ProductionRecipeCreate) -> ProductionRecipe:
        material = self.materials.get_by_id(data.material_id)
        if material is None or not material.is_active:
            raise EntityNotFoundError("Material", data.material_id)

        recipe = ProductionRecipe(
            recipe_code=data.recipe_code,
            material_id=data.material_id,
            version=data.version,
        )
        self._recipe_with_bom(recipe, data)
        try:
            created = self.recipes.add(recipe)
            self._session.commit()
            logger.info("Production recipe %s created", created.recipe_code)
            return created
        except IntegrityError:
            self._session.rollback()
            duplicate = self.recipes.get_by_code(data.recipe_code) is not None
            self._session.rollback()
            if duplicate:
                raise DuplicateEntityError("ProductionRecipe", data.recipe_code) from None
            raise DatabaseIntegrityError("ProductionRecipe") from None

    def update_recipe(
        self, id: int, data: ProductionRecipeUpdate
    ) -> ProductionRecipe:
        recipe_stmt = (
            select(ProductionRecipe)
            .where(ProductionRecipe.id == id)
            .with_for_update()
        )
        recipe = self._session.execute(recipe_stmt).scalar_one_or_none()
        if recipe is None:
            raise EntityNotFoundError("ProductionRecipe", id)

        update_data = data.model_dump(exclude_unset=True, mode="python")

        if "material_id" in update_data and update_data["material_id"] is not None:
            new_material_id = update_data["material_id"]
            material = self.materials.get_by_id(new_material_id)
            if material is None or not material.is_active:
                raise EntityNotFoundError("Material", new_material_id)

            if new_material_id != recipe.material_id:
                stmt = (
                    select(ProductionOrder.id)
                    .where(ProductionOrder.recipe_id == id)
                    .limit(1)
                )
                if self._session.execute(stmt).scalar_one_or_none() is not None:
                    self._session.rollback()
                    raise EntityHasDependenciesError(
                        "ProductionRecipe", recipe.recipe_code, ["production_orders"]
                    )

        candidate_recipe_code = update_data.get("recipe_code", recipe.recipe_code)
        try:
            if data.components is not None:
                recipe.components = []
                for component in data.components:
                    self._validate_component(component.component_material_id, component.unit)
                    recipe.components.append(
                        RecipeComponent(
                            component_material_id=component.component_material_id,
                            quantity=component.quantity,
                            unit=component.unit,
                        )
                    )

            if data.operations is not None:
                recipe.operations = []
                for operation in data.operations:
                    recipe.operations.append(
                        RecipeOperation(
                            sequence=operation.sequence,
                            work_center=operation.work_center,
                            operation_description=operation.operation_description,
                            standard_time_minutes=operation.standard_time_minutes,
                        )
                    )

            for key, value in update_data.items():
                if key in ("components", "operations"):
                    continue
                setattr(recipe, key, value)

            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            existing = self.recipes.get_by_code(candidate_recipe_code)
            self._session.rollback()
            if existing is not None and existing.id != id:
                raise DuplicateEntityError(
                    "ProductionRecipe", candidate_recipe_code
                ) from None
            raise DatabaseIntegrityError("ProductionRecipe") from None
        except Exception:
            self._session.rollback()
            raise

        logger.info("Production recipe %s updated", recipe.recipe_code)
        return recipe

    def delete_recipe(self, id: int) -> None:
        recipe = self.recipes.get_by_id(id)
        if recipe is None:
            raise EntityNotFoundError("ProductionRecipe", id)

        stmt = (
            select(ProductionOrder.id)
            .where(ProductionOrder.recipe_id == id)
            .limit(1)
        )
        if self._session.execute(stmt).scalar_one_or_none() is not None:
            raise EntityHasDependenciesError(
                "ProductionRecipe", recipe.recipe_code, ["production_orders"]
            )

        self._session.delete(recipe)
        self._session.flush()
        self._session.commit()
        logger.info("Production recipe %s deleted", recipe.recipe_code)
