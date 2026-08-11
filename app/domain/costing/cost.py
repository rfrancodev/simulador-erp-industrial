"""Pydantic schemas for CO — Controlling / Costing."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CostRecordBase(BaseModel):
    production_order_id: int = Field(..., gt=0)
    planned_material_cost: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    planned_labor_cost: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    planned_machine_cost: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    planned_energy_cost: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)


class CostRecordCreate(CostRecordBase):
    pass


class CostRecordUpdate(BaseModel):
    actual_material_cost: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    actual_labor_cost: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    actual_machine_cost: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    actual_energy_cost: Optional[Decimal] = Field(None, ge=0, decimal_places=2)


class CostRecord(CostRecordBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actual_material_cost: Optional[Decimal] = None
    actual_labor_cost: Optional[Decimal] = None
    actual_machine_cost: Optional[Decimal] = None
    actual_energy_cost: Optional[Decimal] = None
    actual_total_cost: Optional[Decimal] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    @property
    def variance(self) -> Optional[Decimal]:
        if self.actual_total_cost is None:
            return None
        return self.actual_total_cost - self.planned_total_cost

    @property
    def variance_percent(self) -> Optional[Decimal]:
        if self.actual_total_cost is None or self.planned_total_cost == 0:
            return None
        return ((self.actual_total_cost - self.planned_total_cost) / self.planned_total_cost) * 100


class CostSummary(BaseModel):
    planned_total: Decimal
    actual_total: Optional[Decimal] = None
    variance: Optional[Decimal] = None
    variance_percent: Optional[Decimal] = None
