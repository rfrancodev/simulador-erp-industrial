"""REST API router for CO — Controlling / Cost Management domain."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.connection import session_dependency
from app.domain.common import PaginatedResponse, paginate
from app.domain.costing.cost import (
    CostRecord,
    CostRecordCreate,
    CostRecordUpdate,
    CostSummary,
)
from app.security.dependencies import require_api_access
from app.services.costing_service import CostingService

router = APIRouter(
    prefix="/api/costing",
    tags=["CO"],
    dependencies=[Depends(require_api_access)],
)


def _svc(session: Session = Depends(session_dependency)) -> CostingService:
    return CostingService(session)


# ── Cost Records ─────────────────────────────────────────────────────────────

@router.get("/records", response_model=PaginatedResponse[CostRecord])
def list_cost_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    svc: CostingService = Depends(_svc),
):
    return paginate(svc.list_cost_records(skip, limit), svc.records.count(), skip, limit)


@router.post("/records", response_model=CostRecord, status_code=201)
def create_cost_record(data: CostRecordCreate, svc: CostingService = Depends(_svc)):
    return svc.create_cost_record(data)


@router.get("/records/{id}", response_model=CostRecord)
def get_cost_record(id: int, svc: CostingService = Depends(_svc)):
    return svc.get_cost_record(id)


@router.get("/records/order/{order_id}", response_model=CostRecord)
def get_cost_record_by_order(order_id: int, svc: CostingService = Depends(_svc)):
    return svc.get_cost_record_by_order(order_id)


@router.put("/records/{id}/actual", response_model=CostRecord)
def update_actual_costs(
    id: int, data: CostRecordUpdate, svc: CostingService = Depends(_svc)
):
    return svc.update_actual_costs(id, data)


@router.get("/records/{id}/summary", response_model=CostSummary)
def get_cost_summary(id: int, svc: CostingService = Depends(_svc)):
    return svc.get_summary(id)