"""REST API router for QM — Quality Management domain."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.connection import session_dependency
from app.domain.quality.inspection import (
    NonConformity,
    NonConformityCreate,
    QualityInspection,
    QualityInspectionCreate,
    QualityInspectionResult,
)
from app.services.quality_service import QualityService

router = APIRouter(prefix="/api/quality", tags=["QM"])


def _svc(session: Session = Depends(session_dependency)) -> QualityService:
    return QualityService(session)


# ── Quality Inspections ────────────────────────────────────────────────────

@router.get("/inspections", response_model=list[QualityInspection])
def list_inspections(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    svc: QualityService = Depends(_svc),
):
    return svc.list_inspections(skip, limit)


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

@router.get("/inspections/{id}/non-conformities", response_model=list[NonConformity])
def list_non_conformities(id: int, svc: QualityService = Depends(_svc)):
    return svc.list_non_conformities(id)


@router.post("/inspections/{id}/non-conformities", response_model=NonConformity, status_code=201)
def add_non_conformity(
    id: int, data: NonConformityCreate, svc: QualityService = Depends(_svc)
):
    return svc.add_non_conformity(id, data)