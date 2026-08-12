"""SQLAlchemy ORM models for PP-PI, QM and CO domains.

All status/type string columns are constrained via CHECK constraints that are
derived from the Pydantic enums (M-01). Monetary totals are validated by CHECK
constraints so stored values can never drift from their components (H-02).
Timestamps are timezone-aware UTC (M-06).
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain.production.batch import BatchStatus
from app.domain.production.material import MaterialType
from app.domain.production.recipe import ProductionOrderStatus
from app.domain.quality.inspection import DefectDisposition, DefectSeverity, InspectionStatus


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _enum_check(name: str, column: str, enum_cls: type) -> CheckConstraint:
    values = ", ".join(f"'{v.value}'" for v in enum_cls)
    return CheckConstraint(f"{column} IN ({values})", name=name)


class Base(DeclarativeBase):
    pass


class Material(Base):
    __tablename__ = "materials"
    __table_args__ = (
        _enum_check("ck_materials_material_type", "material_type", MaterialType),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_code: Mapped[str] = mapped_column(String(18), unique=True, nullable=False, index=True)
    material_name: Mapped[str] = mapped_column(String(100), nullable=False)
    material_type: Mapped[str] = mapped_column(String(50), nullable=False)
    base_unit: Mapped[str] = mapped_column(String(3), nullable=False)
    plant: Mapped[str] = mapped_column(String(4), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=_utcnow)

    recipes: Mapped[list["ProductionRecipe"]] = relationship(back_populates="material")
    production_orders: Mapped[list["ProductionOrder"]] = relationship(back_populates="material")


class ProductionRecipe(Base):
    __tablename__ = "production_recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipe_code: Mapped[str] = mapped_column(String(18), unique=True, nullable=False, index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False)
    version: Mapped[str] = mapped_column(String(10), nullable=False, default="1.0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())

    material: Mapped["Material"] = relationship(back_populates="recipes")
    components: Mapped[list["RecipeComponent"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )
    operations: Mapped[list["RecipeOperation"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )


class RecipeComponent(Base):
    __tablename__ = "recipe_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("production_recipes.id"), nullable=False)
    component_material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(3), nullable=False)

    recipe: Mapped["ProductionRecipe"] = relationship(back_populates="components")


class RecipeOperation(Base):
    __tablename__ = "recipe_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("production_recipes.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    work_center: Mapped[str] = mapped_column(String(8), nullable=False)
    operation_description: Mapped[str] = mapped_column(String(200), nullable=False)
    standard_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    recipe: Mapped["ProductionRecipe"] = relationship(back_populates="operations")


class ProductionOrder(Base):
    __tablename__ = "production_orders"
    __table_args__ = (
        _enum_check("ck_production_orders_status", "status", ProductionOrderStatus),
        CheckConstraint("planned_end > planned_start", name="ck_production_orders_dates"),
        CheckConstraint("planned_quantity > 0", name="ck_production_orders_planned_qty"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_number: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("production_recipes.id"), nullable=False)
    planned_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    actual_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    planned_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="CREATED", server_default=text("'CREATED'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())

    material: Mapped["Material"] = relationship(back_populates="production_orders")
    recipe: Mapped["ProductionRecipe"] = relationship()
    batches: Mapped[list["Batch"]] = relationship(back_populates="production_order")
    cost_record: Mapped[Optional["CostRecord"]] = relationship(back_populates="production_order", uselist=False)


class ProductionResource(Base):
    __tablename__ = "production_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False, index=True)
    resource_name: Mapped[str] = mapped_column(String(50), nullable=False)
    work_center: Mapped[str] = mapped_column(String(8), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)

    batches: Mapped[list["Batch"]] = relationship(back_populates="resource")


class Batch(Base):
    __tablename__ = "batches"
    __table_args__ = (
        _enum_check("ck_batches_status", "status", BatchStatus),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_number: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    production_order_id: Mapped[int] = mapped_column(ForeignKey("production_orders.id"), nullable=False)
    resource_id: Mapped[int] = mapped_column(ForeignKey("production_resources.id"), nullable=False)
    planned_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    actual_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    yield_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="CREATED", server_default=text("'CREATED'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    production_order: Mapped["ProductionOrder"] = relationship(back_populates="batches")
    resource: Mapped["ProductionResource"] = relationship(back_populates="batches")
    quality_inspection: Mapped[Optional["QualityInspection"]] = relationship(back_populates="batch", uselist=False)


class ProductionConfirmation(Base):
    __tablename__ = "production_confirmations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), nullable=False)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(3), nullable=False)
    confirmation_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class MaterialConsumption(Base):
    __tablename__ = "material_consumptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), nullable=False)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(3), nullable=False)
    consumption_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# QM domain models
class QualityInspection(Base):
    __tablename__ = "quality_inspections"
    __table_args__ = (
        _enum_check("ck_quality_inspections_status", "inspection_status", InspectionStatus),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), nullable=False, unique=True)
    inspection_lot: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    inspection_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", server_default=text("'PENDING'"))
    pH: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2), nullable=True)
    alcohol_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 1), nullable=True)
    temperature: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 1), nullable=True)
    co2_level: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    appearance: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    microbiological_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    inspector_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    inspection_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    result_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    batch: Mapped["Batch"] = relationship(back_populates="quality_inspection")
    non_conformities: Mapped[list["NonConformity"]] = relationship(back_populates="inspection")


class NonConformity(Base):
    __tablename__ = "non_conformities"
    __table_args__ = (
        _enum_check("ck_non_conformities_severity", "severity", DefectSeverity),
        _enum_check("ck_non_conformities_disposition", "disposition", DefectDisposition),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inspection_id: Mapped[int] = mapped_column(ForeignKey("quality_inspections.id"), nullable=False)
    defect_type: Mapped[str] = mapped_column(String(50), nullable=False)
    defect_code: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    disposition: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())

    inspection: Mapped["QualityInspection"] = relationship(back_populates="non_conformities")


# CO domain models
class CostRecord(Base):
    __tablename__ = "cost_records"
    __table_args__ = (
        CheckConstraint(
            "planned_total_cost = "
            "planned_material_cost + planned_labor_cost + planned_machine_cost + planned_energy_cost",
            name="ck_cost_planned_total",
        ),
        CheckConstraint(
            "actual_total_cost IS NULL OR actual_total_cost = "
            "COALESCE(actual_material_cost, 0) + COALESCE(actual_labor_cost, 0) "
            "+ COALESCE(actual_machine_cost, 0) + COALESCE(actual_energy_cost, 0)",
            name="ck_cost_actual_total",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    production_order_id: Mapped[int] = mapped_column(ForeignKey("production_orders.id"), nullable=False, unique=True)

    planned_material_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    planned_labor_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    planned_machine_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default=text("0"))
    planned_energy_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default=text("0"))
    planned_total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default=text("0"))

    actual_material_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    actual_labor_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    actual_machine_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    actual_energy_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    actual_total_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=_utcnow)

    production_order: Mapped["ProductionOrder"] = relationship(back_populates="cost_record")

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