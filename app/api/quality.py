"""REST API router for QM — Quality Management domain."""

from typing import TypeVar

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.connection import session_dependency
from app.domain.common import PaginatedResponse
from app.domain.quality.inspection import (
    NonConformity,
    NonConformityCreate,
    QualityInspection,
    QualityInspectionCreate,
    QualityInspectionResult,
)
from app.services.quality_service import QualityService

router = APIRouter(prefix="/api/quality", tags=["QM"])

T = TypeVar("T")


def _svc(session: Session = Depends(session_dependency)) -> QualityService:
    return QualityService(session)


def _paginate(items: list[T], total: int, skip: int, limit: int) -> PaginatedResponse[T]:
    return PaginatedResponse(
        items=items,
        total=total,
        page=skip // limit + 1 if limit > 0 else 1,
        page_size=limit,
    )


# ── Quality Inspections ────────────────────────────────────────────────────

@router.get("/inspections", response_model=PaginatedResponse[QualityInspection])
def list_inspections(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    svc: QualityService = Depends(_svc),
):
    return _paginate(
        svc.list_inspections(skip, limit), svc.inspections.count(), skip, limit
    )


@router.post("/inspections", response_model=QualityInspection, status_code=201)
def create_inspection(data: QualityInspectionCreate, svc: QualityService = Depends(_svc)):
    return svc.create_inspection(data)


@router.get("/inspections/{id}", response_model=QualityInspection)
def get_inspection(id: int, svc: QualityService = Depends(_svc)):
    return svc.get_inspection(id)


@router.get("/inspections/lot/{inspection_lot}", response_model=QualityInspection)
def get_inspection_by_lot(inspection_lot: str, svc: QualityService = Depends(_svc)):
    return svc.get_inspection_by_lot(inspection_lot)


@router.get("/inspections/batch/{batch_id}", response_model=QualityInspection)
def get_inspection_by_batch(batch_id: int, svc: QualityService = Depends(_svc)):
    return svc.get_inspection_by_batch(batch_id)


@router.put("/inspections/{id}/result", response_model=QualityInspection)
def update_inspection_result(
    id: int, data: QualityInspectionResult, svc: QualityService = Depends(_svc)
):
    return svc.update_inspection_result(id, data)


# ── Non-Conformities ───────────────────────────────────────────────────────

@router.get("/inspections/{id}/non-conformities", response_model=PaginatedResponse[NonConformity])
def list_non_conformities(
    id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    svc: QualityService = Depends(_svc),
):
    return _paginate(
        svc.list_non_conformities(id),
        svc.non_conformities.count_by_inspection(id),
        skip,
        limit,
    )


@router.post("/inspections/{id}/non-conformities", response_model=NonConformity, status_code=201)
def add_non_conformity(
    id: int, data: NonConformityCreate, svc: QualityService = Depends(_svc)
):
    return svc.add_non_conformity(id, data)