"""CO data generator — cost records (planned vs actual).

The planned material cost is derived from the recipe BOM (component quantity x
unit price), reconciling PP-PI consumption with CO cost. Labor, machine and
energy are synthetic per-liter overheads. Actual costs add a random variance
plus a rework factor when a quality inspection failed (QM -> CO).

Synthetic data — for educational and simulation purposes only.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.entities import CostRecord, ProductionOrder
from app.simulation.config import (
    STANDARD_BATCH_LITERS,
    MonthParams,
    SimulationContext,
    to_decimal,
)

# Synthetic unit prices (R$) per material code — used to price the BOM.
_MATERIAL_PRICES = {
    "RAW-WATER": Decimal("0.05"),
    "RAW-MALT": Decimal("4.00"),
    "RAW-HOPS": Decimal("80.00"),
    "RAW-YEAST": Decimal("30.00"),
    "RAW-CO2": Decimal("10.00"),
    "PKG-BOTTLE": Decimal("0.30"),
    "PKG-LABEL": Decimal("0.05"),
    "PKG-CAP": Decimal("0.08"),
}

# Synthetic per-liter overhead costs (R$ per liter of finished product).
_LABOR_COST_PER_L = Decimal("0.35")
_MACHINE_COST_PER_L = Decimal("0.30")
_ENERGY_COST_PER_L = Decimal("0.18")

# Extra cost factor applied when a quality failure triggers rework/scrap (QM→CO).
_REWORK_COST_FACTOR = Decimal("0.08")


def _planned_material_cost(ctx: SimulationContext, order: ProductionOrder) -> Decimal:
    recipe = ctx.recipe_by_id.get(order.recipe_id)
    if recipe is None:
        return Decimal("0")
    bom_cost = sum(
        (
            component.quantity
            * _MATERIAL_PRICES.get(
                ctx.material_code_by_id.get(component.component_material_id, ""), Decimal("0")
            )
        )
        for component in recipe.components
    )
    scale = order.planned_quantity / STANDARD_BATCH_LITERS
    return (bom_cost * scale).quantize(Decimal("0.01"))


def generate_cost_record(
    ctx: SimulationContext,
    order: ProductionOrder,
    quality_failed: bool,
    params: MonthParams,
) -> CostRecord:
    """Create a cost record with planned and actual costs for an order."""
    rng = ctx.rng
    qty = order.planned_quantity

    planned_material = _planned_material_cost(ctx, order)
    planned_labor = (qty * _LABOR_COST_PER_L).quantize(Decimal("0.01"))
    planned_machine = (qty * _MACHINE_COST_PER_L).quantize(Decimal("0.01"))
    planned_energy = (qty * _ENERGY_COST_PER_L).quantize(Decimal("0.01"))

    variance = rng.gauss(params.cost_variance, 0.01)
    factor = Decimal("1") + to_decimal(variance, 4)
    if quality_failed:
        factor += _REWORK_COST_FACTOR

    actual_material = (planned_material * factor).quantize(Decimal("0.01"))
    actual_labor = (planned_labor * factor).quantize(Decimal("0.01"))
    actual_machine = (planned_machine * factor).quantize(Decimal("0.01"))
    actual_energy = (planned_energy * factor).quantize(Decimal("0.01"))

    record = CostRecord(
        production_order_id=order.id,
        planned_material_cost=planned_material,
        planned_labor_cost=planned_labor,
        planned_machine_cost=planned_machine,
        planned_energy_cost=planned_energy,
        planned_total_cost=planned_material + planned_labor + planned_machine + planned_energy,
        actual_material_cost=actual_material,
        actual_labor_cost=actual_labor,
        actual_machine_cost=actual_machine,
        actual_energy_cost=actual_energy,
        actual_total_cost=actual_material + actual_labor + actual_machine + actual_energy,
    )
    ctx.session.add(record)
    ctx.summary.cost_records += 1
    return record
