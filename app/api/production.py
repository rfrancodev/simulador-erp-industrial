"""REST API router for PP-PI — Production domain."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.connection import session_dependency
from app.domain.common import PaginatedResponse, paginate
from app.domain.production.batch import Batch, BatchCreate, ProductionResource, ProductionResourceCreate
from app.domain.production.material import Material, MaterialCreate, MaterialUpdate
from app.domain.production.recipe import (
    ProductionOrder,
    ProductionOrderCreate,
    ProductionOrderStatus,
    ProductionRecipe,
    ProductionRecipeCreate,
    ProductionRecipeUpdate,
)
from app.services.production_service import ProductionService

router = APIRouter(prefix="/api/production", tags=["PP-PI"])


def _svc(session: Session = Depends(session_dependency)) -> ProductionService:
    return ProductionService(session)


# ── Materials ────────────────────────────────────────────────────────────

@router.get("/materials", response_model=PaginatedResponse[Material])
def list_materials(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    active: Optional[bool] = Query(True, description="Filter by active status: true, false, or omit for active only"),
    svc: ProductionService = Depends(_svc),
):
    materials = svc.list_materials(skip, limit, active=active)
    if active is True:
        total = svc.materials.count_active()
    elif active is False:
        total = svc.materials.count_inactive()
    else:
        total = svc.materials.count_all()
    return paginate(materials, total, skip, limit)


@router.get("/materials/{id}", response_model=Material)
def get_material(id: int, svc: ProductionService = Depends(_svc)):
    return svc.get_material(id)


@router.post("/materials", response_model=Material, status_code=201)
def create_material(data: MaterialCreate, svc: ProductionService = Depends(_svc)):
    return svc.create_material(data)


@router.put("/materials/{id}", response_model=Material)
def update_material(id: int, data: MaterialUpdate, svc: ProductionService = Depends(_svc)):
    return svc.update_material(id, data)


@router.delete("/materials/{id}", status_code=204)
def delete_material(id: int, svc: ProductionService = Depends(_svc)):
    svc.delete_material(id)


# ── Production Orders ────────────────────────────────────────────────────

@router.get("/orders", response_model=PaginatedResponse[ProductionOrder])
def list_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    svc: ProductionService = Depends(_svc),
):
    return paginate(
        svc.list_orders(skip, limit), svc.orders.count(), skip, limit
    )


@router.get("/orders/{id}", response_model=ProductionOrder)
def get_order(id: int, svc: ProductionService = Depends(_svc)):
    return svc.get_order(id)


@router.get("/orders/number/{order_number}", response_model=ProductionOrder)
def get_order_by_number(order_number: str, svc: ProductionService = Depends(_svc)):
    return svc.get_order_by_number(order_number)


@router.get("/orders/status/{status}", response_model=PaginatedResponse[ProductionOrder])
def list_orders_by_status(
    status: ProductionOrderStatus,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    svc: ProductionService = Depends(_svc),
):
    return paginate(
        svc.list_orders_by_status(status, skip, limit),
        svc.orders.count_by_status(status.value),
        skip,
        limit,
    )


@router.post("/orders", response_model=ProductionOrder, status_code=201)
def create_production_order(data: ProductionOrderCreate, svc: ProductionService = Depends(_svc)):
    return svc.create_production_order(data)


# ── Batches ──────────────────────────────────────────────────────────────

@router.get("/batches/order/{order_id}", response_model=PaginatedResponse[Batch])
def list_batches_by_order(
    order_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    svc: ProductionService = Depends(_svc),
):
    return paginate(
        svc.list_batches_by_order(order_id, skip, limit),
        svc.batches.count_by_order(order_id),
        skip,
        limit,
    )


@router.get("/batches/number/{batch_number}", response_model=Batch)
def get_batch_by_number(batch_number: str, svc: ProductionService = Depends(_svc)):
    return svc.get_batch_by_number(batch_number)


@router.post("/batches", response_model=Batch, status_code=201)
def create_batch(data: BatchCreate, svc: ProductionService = Depends(_svc)):
    return svc.create_batch(data)


# ── Production Resources ─────────────────────────────────────────────────

@router.get("/resources", response_model=PaginatedResponse[ProductionResource])
def list_resources(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    svc: ProductionService = Depends(_svc),
):
    return paginate(
        svc.list_resources(skip, limit), svc.resources.count(), skip, limit
    )


@router.get("/resources/{id}", response_model=ProductionResource)
def get_resource(id: int, svc: ProductionService = Depends(_svc)):
    return svc.get_resource(id)


@router.get("/resources/code/{code}", response_model=ProductionResource)
def get_resource_by_code(code: str, svc: ProductionService = Depends(_svc)):
    return svc.get_resource_by_code(code)


@router.get("/resources/work-center/{work_center}", response_model=PaginatedResponse[ProductionResource])
def list_resources_by_work_center(
    work_center: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    svc: ProductionService = Depends(_svc),
):
    return paginate(
        svc.list_resources_by_work_center(work_center, skip, limit),
        svc.resources.count_by_work_center(work_center),
        skip,
        limit,
    )


@router.post("/resources", response_model=ProductionResource, status_code=201)
def create_resource(data: ProductionResourceCreate, svc: ProductionService = Depends(_svc)):
    return svc.create_resource(data)


# ── Production Recipes ───────────────────────────────────────────────────

@router.get("/recipes", response_model=PaginatedResponse[ProductionRecipe])
def list_recipes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    svc: ProductionService = Depends(_svc),
):
    return paginate(
        svc.list_recipes(skip, limit), svc.recipes.count(), skip, limit
    )


@router.get("/recipes/{id}", response_model=ProductionRecipe)
def get_recipe(id: int, svc: ProductionService = Depends(_svc)):
    return svc.get_recipe(id)


@router.get("/recipes/code/{code}", response_model=ProductionRecipe)
def get_recipe_by_code(code: str, svc: ProductionService = Depends(_svc)):
    return svc.get_recipe_by_code(code)


@router.get("/recipes/material/{material_id}", response_model=PaginatedResponse[ProductionRecipe])
def list_active_recipes_for_material(
    material_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    svc: ProductionService = Depends(_svc),
):
    return paginate(
        svc.list_active_recipes_for_material(material_id, skip, limit),
        svc.recipes.count_active_for_material(material_id),
        skip,
        limit,
    )


@router.post("/recipes", response_model=ProductionRecipe, status_code=201)
def create_recipe(data: ProductionRecipeCreate, svc: ProductionService = Depends(_svc)):
    return svc.create_recipe(data)


@router.put("/recipes/{id}", response_model=ProductionRecipe)
def update_recipe(
    id: int, data: ProductionRecipeUpdate, svc: ProductionService = Depends(_svc)
):
    return svc.update_recipe(id, data)


@router.delete("/recipes/{id}", status_code=204)
def delete_recipe(id: int, svc: ProductionService = Depends(_svc)):
    svc.delete_recipe(id)