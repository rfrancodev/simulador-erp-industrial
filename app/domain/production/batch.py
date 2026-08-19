"""Pydantic schemas for PP-PI — Batch and Production Confirmation."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BatchStatus(str, Enum):
    CREATED = "CREATED"
    IN_PRODUCTION = "IN_PRODUCTION"
    COMPLETED = "COMPLETED"
    REWORK = "REWORK"
    SCRAP = "SCRAP"
    RELEASED = "RELEASED"


class ProductionResourceBase(BaseModel):
    resource_code: str = Field(..., max_length=8)
    resource_name: str = Field(..., max_length=50)
    work_center: str = Field(..., max_length=8)
    resource_type: str = Field(..., max_length=30)


class ProductionResourceCreate(ProductionResourceBase):
    pass


class ProductionResource(ProductionResourceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_available: bool


class BatchBase(BaseModel):
    batch_number: str = Field(..., min_length=1, max_length=16)
    production_order_id: int = Field(..., gt=0)
    resource_id: int = Field(..., gt=0)
    planned_quantity: Decimal = Field(..., gt=0, decimal_places=3)


class BatchCreate(BatchBase):
    pass


class BatchStatusUpdate(BaseModel):
    status: BatchStatus


class Batch(BatchBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actual_quantity: Optional[Decimal] = None
    yield_percent: Optional[Decimal] = None
    status: BatchStatus
    created_at: datetime
    completed_at: Optional[datetime] = None


class ProductionConfirmationBase(BaseModel):
    batch_id: int = Field(..., gt=0)
    operation: str = Field(..., max_length=100)
    quantity: Decimal = Field(..., gt=0, decimal_places=3)
    unit: str = Field(..., max_length=3)
    confirmation_time: datetime
    is_final: bool = False
    notes: Optional[str] = None


class ProductionConfirmationCreate(ProductionConfirmationBase):
    pass


class ProductionConfirmation(ProductionConfirmationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class MaterialConsumptionBase(BaseModel):
    batch_id: int = Field(..., gt=0)
    material_id: int = Field(..., gt=0)
    quantity: Decimal = Field(..., gt=0, decimal_places=3)
    unit: str = Field(..., max_length=3)
    consumption_time: datetime


class MaterialConsumptionCreate(MaterialConsumptionBase):
    pass


class MaterialConsumption(MaterialConsumptionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
