"""Pydantic schemas for PP-PI — Material entity."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MaterialType(str, Enum):
    FINISHED_PRODUCT = "FINISHED_PRODUCT"
    RAW_MATERIAL = "RAW_MATERIAL"
    SEMI_FINISHED = "SEMI_FINISHED"
    PACKAGING = "PACKAGING"
    AUXILIARY = "AUXILIARY"


class MaterialBase(BaseModel):
    material_code: str = Field(..., min_length=1, max_length=18, description="Unique material code (SAP-style)")
    material_name: str = Field(..., min_length=1, max_length=100, description="Material description")
    material_type: MaterialType = Field(..., description="Material type classification")
    base_unit: str = Field(..., min_length=1, max_length=3, description="Base unit of measure (e.g., L, KG, PC)")
    plant: str = Field(..., min_length=1, max_length=4, description="Production plant code")


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(BaseModel):
    material_name: Optional[str] = Field(None, min_length=1, max_length=100)
    material_type: Optional[MaterialType] = None
    is_active: Optional[bool] = None


class Material(MaterialBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
