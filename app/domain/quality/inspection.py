"""Pydantic schemas for QM — Quality Management."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class InspectionStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    PASSED = "PASSED"
    FAILED = "FAILED"
    REWORK = "REWORK"
    SCRAP = "SCRAP"


class DefectSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class DefectDisposition(str, Enum):
    USE_AS_IS = "USE_AS_IS"
    REWORK = "REWORK"
    SCRAP = "SCRAP"
    RETURN = "RETURN"


class QualityInspectionBase(BaseModel):
    batch_id: int = Field(..., gt=0)
    inspection_lot: str = Field(..., min_length=1, max_length=16)


class QualityInspectionCreate(QualityInspectionBase):
    pass


class QualityInspectionResult(BaseModel):
    inspection_status: InspectionStatus
    pH: Optional[Decimal] = Field(None, ge=0, le=14, decimal_places=2)
    alcohol_percent: Optional[Decimal] = Field(None, ge=0, le=100, decimal_places=1)
    temperature: Optional[Decimal] = Field(None, decimal_places=1)
    co2_level: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    appearance: Optional[str] = None
    microbiological_status: Optional[str] = None
    inspector_notes: Optional[str] = None


class QualityInspection(QualityInspectionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    inspection_status: InspectionStatus
    pH: Optional[Decimal] = None
    alcohol_percent: Optional[Decimal] = None
    temperature: Optional[Decimal] = None
    co2_level: Optional[Decimal] = None
    appearance: Optional[str] = None
    microbiological_status: Optional[str] = None
    inspector_notes: Optional[str] = None
    inspection_date: datetime
    result_date: Optional[datetime] = None


class NonConformityBase(BaseModel):
    defect_type: str = Field(..., max_length=50)
    defect_code: str = Field(..., max_length=10)
    description: str = Field(..., max_length=200)
    severity: DefectSeverity
    disposition: DefectDisposition


class NonConformityCreate(NonConformityBase):
    pass


class NonConformity(NonConformityBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    inspection_id: int
    created_at: datetime
