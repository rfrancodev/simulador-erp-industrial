"""Repository for PP-PI — Production domain."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import EntityHasDependenciesError
from app.domain.entities import (
    Batch,
    Material,
    MaterialConsumption,
    ProductionOrder,
    ProductionRecipe,
    ProductionResource,
    RecipeComponent,
)
from app.domain.production.material import MaterialCreate, MaterialUpdate
from app.repositories.base import BaseRepository


class MaterialRepository(BaseRepository[Material]):
    # Models whose foreign keys reference Material and therefore block deletion.
    _DEPENDENT_MODELS: tuple[tuple[type, str], ...] = (
        (ProductionRecipe, "material_id"),
        (RecipeComponent, "component_material_id"),
        (ProductionOrder, "material_id"),
        (MaterialConsumption, "material_id"),
    )

    def __init__(self, session: Session):
        super().__init__(Material, session)

    def get_by_code(self, code: str) -> Material | None:
        stmt = select(Material).where(Material.material_code == code)
        return self._session.execute(stmt).scalar_one_or_none()

    def create(self, data: MaterialCreate) -> Material:
        material = Material(
            material_code=data.material_code,
            material_name=data.material_name,
            material_type=data.material_type.value,
            base_unit=data.base_unit,
            plant=data.plant,
        )
        return self.add(material)

    def update(self, id: int, data: MaterialUpdate) -> Material | None:
        material = self.get_by_id(id)
        if material is None:
            return None
        update_data = data.model_dump(exclude_unset=True)
        if "material_type" in update_data and update_data["material_type"] is not None:
            update_data["material_type"] = update_data["material_type"].value
        for key, value in update_data.items():
            setattr(material, key, value)
        self._session.flush()
        self._session.refresh(material)
        return material

    def delete(self, id: int) -> bool:
        material = self.get_by_id(id)
        if material is None:
            return False
        dependencies: list[str] = []
        for model, fk_column in self._DEPENDENT_MODELS:
            stmt = select(model.id).where(getattr(model, fk_column) == id).limit(1)
            if self._session.execute(stmt).scalar_one_or_none() is not None:
                dependencies.append(model.__tablename__)
        if dependencies:
            raise EntityHasDependenciesError("Material", material.material_code, dependencies)
        self._session.delete(material)
        self._session.flush()
        return True

    def list_active(self, skip: int = 0, limit: int = 100) -> list[Material]:
        stmt = select(Material).where(Material.is_active == True).offset(skip).limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def count_active(self) -> int:
        stmt = select(func.count()).select_from(Material).where(Material.is_active == True)
        return self._session.scalar(stmt) or 0


class ProductionOrderRepository(BaseRepository[ProductionOrder]):
    def __init__(self, session: Session):
        super().__init__(ProductionOrder, session)

    def get_by_number(self, order_number: str) -> ProductionOrder | None:
        stmt = select(ProductionOrder).where(ProductionOrder.order_number == order_number)
        return self._session.execute(stmt).scalar_one_or_none()

    def get_with_material(self, id: int) -> ProductionOrder | None:
        stmt = (
            select(ProductionOrder)
            .options(joinedload(ProductionOrder.material))
            .where(ProductionOrder.id == id)
        )
        return self._session.execute(stmt).unique().scalar_one_or_none()

    def get_by_status(self, status: str, skip: int = 0, limit: int = 100) -> list[ProductionOrder]:
        stmt = (
            select(ProductionOrder)
            .where(ProductionOrder.status == status)
            .offset(skip)
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars().all())


class BatchRepository(BaseRepository[Batch]):
    def __init__(self, session: Session):
        super().__init__(Batch, session)

    def get_by_number(self, batch_number: str) -> Batch | None:
        stmt = select(Batch).where(Batch.batch_number == batch_number)
        return self._session.execute(stmt).scalar_one_or_none()

    def get_by_order(self, order_id: int) -> list[Batch]:
        stmt = select(Batch).where(Batch.production_order_id == order_id)
        return list(self._session.execute(stmt).scalars().all())


class ProductionRecipeRepository(BaseRepository[ProductionRecipe]):
    def __init__(self, session: Session):
        super().__init__(ProductionRecipe, session)

    def get_by_code(self, code: str) -> ProductionRecipe | None:
        stmt = select(ProductionRecipe).where(ProductionRecipe.recipe_code == code)
        return self._session.execute(stmt).scalar_one_or_none()

    def get_active_for_material(self, material_id: int) -> list[ProductionRecipe]:
        stmt = (
            select(ProductionRecipe)
            .where(ProductionRecipe.material_id == material_id, ProductionRecipe.is_active == True)
        )
        return list(self._session.execute(stmt).scalars().all())


class ProductionResourceRepository(BaseRepository[ProductionResource]):
    def __init__(self, session: Session):
        super().__init__(ProductionResource, session)

    def get_by_code(self, code: str) -> ProductionResource | None:
        stmt = select(ProductionResource).where(ProductionResource.resource_code == code)
        return self._session.execute(stmt).scalar_one_or_none()

    def get_by_work_center(self, work_center: str) -> list[ProductionResource]:
        stmt = select(ProductionResource).where(ProductionResource.work_center == work_center)
        return list(self._session.execute(stmt).scalars().all())
