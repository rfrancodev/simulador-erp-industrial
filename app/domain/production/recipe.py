"""Pydantic schemas for PP-PI — Production Recipe entity."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProductionOrderStatus(str, Enum):
    CREATED = "CREATED"
    RELEASED = "RELEASED"
    IN_PROCESS = "IN_PROCESS"
    COMPLETED = "COMPLETED"
    CLOSED = "CLOSED"
    DELIVERED = "DELIVERED"
    PARTIAL = "PARTIAL"


class RecipeComponentBase(BaseModel):
    component_material_id: int = Field(..., gt=0)
    quantity: Decimal = Field(..., gt=0, decimal_places=3)
    unit: str = Field(..., max_length=3)


class RecipeOperationBase(BaseModel):
    sequence: int = Field(..., ge=1)
    work_center: str = Field(..., max_length=8)
    operation_description: str = Field(..., max_length=200)
    standard_time_minutes: int = Field(..., ge=1)


class ProductionRecipeBase(BaseModel):
    recipe_code: str = Field(..., min_length=1, max_length=18)
    material_id: int = Field(..., gt=0)
    version: str = Field(default="1.0", max_length=10)


class ProductionRecipeCreate(ProductionRecipeBase):
    components: list[RecipeComponentBase] = []
    operations: list[RecipeOperationBase] = []


class ProductionRecipeUpdate(BaseModel):
    recipe_code: Optional[str] = Field(None, min_length=1, max_length=18)
    material_id: Optional[int] = Field(None, gt=0)
    version: Optional[str] = Field(None, max_length=10)
    is_active: Optional[bool] = None
    components: Optional[list[RecipeComponentBase]] = None
    operations: Optional[list[RecipeOperationBase]] = None


class ProductionRecipe(ProductionRecipeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    components: list[RecipeComponentBase] = []
    operations: list[RecipeOperationBase] = []


class ProductionOrderBase(BaseModel):
    order_number: str = Field(..., min_length=1, max_length=16)
    material_id: int = Field(..., gt=0)
    recipe_id: int = Field(..., gt=0)
    planned_quantity: Decimal = Field(..., gt=0, decimal_places=3)
    planned_start: datetime
    planned_end: datetime

    @model_validator(mode="after")
    def validate_planned_dates(self) -> "ProductionOrderBase":
        if self.planned_end <= self.planned_start:
            raise ValueError("planned_end must be after planned_start")
        return self


class ProductionOrderCreate(ProductionOrderBase):
    pass


class ProductionOrder(ProductionOrderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: ProductionOrderStatus
    actual_quantity: Optional[Decimal] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    recipe: Optional[ProductionRecipe] = None
    created_at: datetime
