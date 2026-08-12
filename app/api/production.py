"""REST API router for PP-PI — Production domain."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.connection import session_dependency
from app.domain.production.batch import Batch, BatchCreate, ProductionResource, ProductionResourceCreate
from app.domain.production.material import Material, MaterialCreate, MaterialList, MaterialUpdate
from app.domain.production.recipe import ProductionOrder, ProductionOrderCreate, ProductionRecipe
from app.services.production_service import ProductionService

router = APIRouter(prefix="/api/production", tags=["PP-PI"])


def _svc(session: Session = Depends(session_dependency)) -> ProductionService:
    return ProductionService(session)


# ── Materials ────────────────────────────────────────────────────────────

@router.get("/materials", response_model=MaterialList)
def list_materials(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    svc: ProductionService = Depends(_svc),
):
    items = svc.list_materials(skip, limit)
    return MaterialList(
        items=items,
        total=svc.materials.count_active(),
        page=skip // limit + 1 if limit > 0 else 1,
        page_size=limit,
    )


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

@router.get("/orders", response_model=list[ProductionOrder])
def list_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    svc: ProductionService = Depends(_svc),
):
    return svc.list_orders(skip, limit)


@router.get("/orders/{id}", response_model=ProductionOrder)
def get_order(id: int, svc: ProductionService = Depends(_svc)):
    return svc.get_order(id)


@router.get("/orders/number/{order_number}", response_model=ProductionOrder)
def get_order_by_number(order_number: str, svc: ProductionService = Depends(_svc)):
    return svc.get_order_by_number(order_number)


@router.get("/orders/status/{status}", response_model=list[ProductionOrder])
def list_orders_by_status(
    status: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    svc: ProductionService = Depends(_svc),
):
    return svc.list_orders_by_status(status, skip, limit)


@router.post("/orders", response_model=ProductionOrder, status_code=201)
def create_production_order(data: ProductionOrderCreate, svc: ProductionService = Depends(_svc)):
    return svc.create_production_order(data)


# ── Batches ──────────────────────────────────────────────────────────────

@router.get("/batches/order/{order_id}", response_model=list[Batch])
def list_batches_by_order(order_id: int, svc: ProductionService = Depends(_svc)):
    return svc.list_batches_by_order(order_id)


@router.get("/batches/number/{batch_number}", response_model=Batch)
def get_batch_by_number(batch_number: str, svc: ProductionService = Depends(_svc)):
    return svc.get_batch_by_number(batch_number)


@router.post("/batches", response_model=Batch, status_code=201)
def create_batch(data: BatchCreate, svc: ProductionService = Depends(_svc)):
    return svc.create_batch(data)


# ── Production Resources ─────────────────────────────────────────────────

@router.get("/resources", response_model=list[ProductionResource])
def list_resources(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    svc: ProductionService = Depends(_svc),
):
    return svc.list_resources(skip, limit)


@router.get("/resources/{id}", response_model=ProductionResource)
def get_resource(id: int, svc: ProductionService = Depends(_svc)):
    return svc.get_resource(id)


@router.get("/resources/code/{code}", response_model=ProductionResource)
def get_resource_by_code(code: str, svc: ProductionService = Depends(_svc)):
    return svc.get_resource_by_code(code)


@router.get("/resources/work-center/{work_center}", response_model=list[ProductionResource])
def list_resources_by_work_center(work_center: str, svc: ProductionService = Depends(_svc)):
    return svc.list_resources_by_work_center(work_center)


@router.post("/resources", response_model=ProductionResource, status_code=201)
def create_resource(data: ProductionResourceCreate, svc: ProductionService = Depends(_svc)):
    return svc.create_resource(data)


# ── Production Recipes ───────────────────────────────────────────────────

@router.get("/recipes", response_model=list[ProductionRecipe])
def list_recipes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    svc: ProductionService = Depends(_svc),
):
    return svc.list_recipes(skip, limit)


@router.get("/recipes/{id}", response_model=ProductionRecipe)
def get_recipe(id: int, svc: ProductionService = Depends(_svc)):
    return svc.get_recipe(id)


@router.get("/recipes/code/{code}", response_model=ProductionRecipe)
def get_recipe_by_code(code: str, svc: ProductionService = Depends(_svc)):
    return svc.get_recipe_by_code(code)


@router.get("/recipes/material/{material_id}", response_model=list[ProductionRecipe])
def list_active_recipes_for_material(material_id: int, svc: ProductionService = Depends(_svc)):
    return svc.list_active_recipes_for_material(material_id)
