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
    EntityNotFoundError,
    RecipeMaterialMismatchError,
)
from app.domain.entities import ProductionOrder
from app.domain.production.recipe import ProductionOrderCreate, ProductionOrderStatus
from app.repositories.production_repository import (
    MaterialRepository,
    ProductionOrderRepository,
    ProductionRecipeRepository,
)

logger = getLogger(__name__)


class ProductionService:
    def __init__(self, session: Session):
        self._session = session
        self.materials = MaterialRepository(session)
        self.recipes = ProductionRecipeRepository(session)
        self.orders = ProductionOrderRepository(session)

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