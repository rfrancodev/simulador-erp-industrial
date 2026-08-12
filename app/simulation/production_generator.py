"""PP-PI data generator — materials, recipes, resources, orders and batches.

Produces the master data (materials/recipes/resources) and the production
records (orders, batches, confirmations and material consumptions). Synthetic
data — for educational and simulation purposes only.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from app.domain.entities import (
    Batch,
    Material,
    MaterialConsumption,
    ProductionConfirmation,
    ProductionOrder,
    ProductionRecipe,
    ProductionResource,
    RecipeComponent,
    RecipeOperation,
)
from app.domain.production.batch import BatchStatus
from app.domain.production.material import MaterialType
from app.domain.production.recipe import ProductionOrderStatus
from app.simulation.config import (
    STANDARD_BATCH_LITERS,
    MonthParams,
    SimulationContext,
    to_decimal,
)

_FINISHED_PRODUCTS = [
    # code, name, alcohol_target_% , hops_kg_per_standard_batch
    ("FIN-BEER-PIL", "Beer Pilsen 600ml", 4.8, 35.0),
    ("FIN-BEER-STO", "Beer Stout 600ml", 6.5, 45.0),
    ("FIN-BEER-IPA", "Beer IPA 600ml", 6.0, 60.0),
]

_RAW_MATERIALS = [
    ("RAW-WATER", "Brewing Water", MaterialType.RAW_MATERIAL, "L"),
    ("RAW-MALT", "Malted Barley", MaterialType.RAW_MATERIAL, "KG"),
    ("RAW-HOPS", "Hops Pellets", MaterialType.RAW_MATERIAL, "KG"),
    ("RAW-YEAST", "Brewing Yeast", MaterialType.RAW_MATERIAL, "KG"),
    ("RAW-CO2", "Carbon Dioxide", MaterialType.RAW_MATERIAL, "KG"),
]

_PACKAGING = [
    ("PKG-BOTTLE", "Glass Bottle 600ml", MaterialType.PACKAGING, "PC"),
    ("PKG-LABEL", "Label 600ml", MaterialType.PACKAGING, "PC"),
    ("PKG-CAP", "Crown Cap", MaterialType.PACKAGING, "PC"),
]

# BOM per standard batch (10,000 L). Hops quantity is overridden per product.
_BOM = [
    ("RAW-WATER", "12000", "L"),
    ("RAW-MALT", "2000", "KG"),
    ("RAW-YEAST", "20", "KG"),
    ("RAW-CO2", "45", "KG"),
    ("PKG-BOTTLE", "16667", "PC"),
    ("PKG-LABEL", "16667", "PC"),
    ("PKG-CAP", "16667", "PC"),
]

_OPERATIONS = [
    (1, "WC-BREW", "Mashing", 90),
    (2, "WC-BREW", "Boiling", 75),
    (3, "WC-FERM", "Fermentation", 10080),
    (4, "WC-FILT", "Filtration", 60),
    (5, "WC-FILL", "Filling", 180),
]

_RESOURCES = [
    ("RES-MASH-01", "Mash Tun 01", "WC-BREW", "MASHER"),
    ("RES-FERM-01", "Fermenter 01", "WC-FERM", "FERMENTER"),
    ("RES-FILT-01", "Filter Press 01", "WC-FILT", "FILTER"),
    ("RES-FILL-01", "Filler Line 01", "WC-FILL", "FILLER"),
    ("RES-FILL-02", "Filler Line 02", "WC-FILL", "FILLER"),
]


def generate_master_data(ctx: SimulationContext) -> None:
    """Create raw materials, packaging, finished products, recipes and resources."""
    for code, name, mtype, unit in _RAW_MATERIALS + _PACKAGING:
        material = Material(
            material_code=code,
            material_name=name,
            material_type=mtype.value,
            base_unit=unit,
            plant="P001",
        )
        ctx.session.add(material)
        ctx.materials[code] = material
        ctx.summary.materials += 1

    for code, name, alcohol_target, hops_kg in _FINISHED_PRODUCTS:
        material = Material(
            material_code=code,
            material_name=name,
            material_type=MaterialType.FINISHED_PRODUCT.value,
            base_unit="L",
            plant="P001",
        )
        ctx.session.add(material)
        ctx.materials[code] = material
        ctx.finished_products.append(material)
        ctx.product_meta[code] = {"alcohol_target": alcohol_target, "hops_kg": hops_kg}
        ctx.summary.materials += 1

    ctx.session.flush()

    for code, material in ctx.materials.items():
        ctx.material_code_by_id[material.id] = code

    for code, _name, _target, hops_kg in _FINISHED_PRODUCTS:
        recipe = ProductionRecipe(
            recipe_code=f"REC-{code}",
            material_id=ctx.materials[code].id,
            version="1.0",
        )
        ctx.session.add(recipe)
        for component_code, quantity, _unit in _BOM:
            if component_code == "RAW-HOPS":
                quantity = str(hops_kg)
            material = ctx.materials[component_code]
            recipe.components.append(
                RecipeComponent(
                    component_material_id=material.id,
                    quantity=Decimal(quantity),
                    unit=material.base_unit,
                )
            )
        for sequence, work_center, description, minutes in _OPERATIONS:
            recipe.operations.append(
                RecipeOperation(
                    sequence=sequence,
                    work_center=work_center,
                    operation_description=description,
                    standard_time_minutes=minutes,
                )
            )
        ctx.recipes[code] = recipe
        ctx.summary.recipes += 1

    for code, name, work_center, resource_type in _RESOURCES:
        resource = ProductionResource(
            resource_code=code,
            resource_name=name,
            work_center=work_center,
            resource_type=resource_type,
        )
        ctx.session.add(resource)
        ctx.resources.append(resource)
        ctx.summary.resources += 1

    ctx.session.flush()
    for code, recipe in ctx.recipes.items():
        ctx.recipe_by_id[recipe.id] = recipe


def generate_month_orders(
    ctx: SimulationContext, month_start: datetime, params: MonthParams
) -> list[ProductionOrder]:
    """Create the production orders scheduled for a single month."""
    orders: list[ProductionOrder] = []
    products = ctx.finished_products
    days_in_month = 28
    for slot in range(ctx.config.orders_per_month):
        product = products[slot % len(products)]
        recipe = ctx.recipes[product.material_code]

        planned_quantity = to_decimal(ctx.rng.uniform(8000, 12000), 3)
        start_day = ctx.rng.randint(1, days_in_month)
        planned_start = month_start.replace(day=start_day) + timedelta(
            hours=ctx.rng.randint(6, 12)
        )
        planned_end = planned_start + timedelta(hours=ctx.rng.randint(24, 72))

        downtime = ctx.rng.random() < params.downtime_probability
        actual_end = (
            planned_end + timedelta(hours=ctx.rng.randint(4, 24)) if downtime else planned_end
        )

        ctx.seq_order += 1
        order = ProductionOrder(
            order_number=f"PO-{month_start.year}-{ctx.seq_order:05d}",
            material_id=product.id,
            recipe_id=recipe.id,
            planned_quantity=planned_quantity,
            planned_start=planned_start,
            planned_end=planned_end,
            status=ProductionOrderStatus.COMPLETED.value,
            actual_start=planned_start + timedelta(hours=ctx.rng.randint(0, 4)),
            actual_end=actual_end,
        )
        ctx.session.add(order)
        orders.append(order)
        ctx.summary.orders += 1
    ctx.session.flush()
    return orders


def _batch_yield(rng, params: MonthParams) -> Decimal:
    value = rng.gauss(params.yield_mean, 0.02)
    value = max(0.5, min(1.0, value))
    if rng.random() < params.failure_rate:
        value *= rng.uniform(0.5, 0.85)
    return to_decimal(value, 4)


def generate_batches(
    ctx: SimulationContext, order: ProductionOrder, params: MonthParams
) -> list[Batch]:
    """Create the batches (with confirmations/consumptions) for an order."""
    recipe = ctx.recipe_by_id.get(order.recipe_id)
    batches: list[Batch] = []
    num_batches = ctx.rng.randint(1, ctx.config.max_batches_per_order)
    per_batch = order.planned_quantity / num_batches

    total_actual = Decimal("0")
    for i in range(num_batches):
        planned_qty = (
            per_batch if i < num_batches - 1 else order.planned_quantity - per_batch * (num_batches - 1)
        ).quantize(Decimal("0.001"))
        yield_pct = _batch_yield(ctx.rng, params)
        actual_qty = (planned_qty * yield_pct).quantize(Decimal("0.001"))
        total_actual += actual_qty

        resource = ctx.resources[ctx.rng.randrange(len(ctx.resources))]
        completed_at = order.actual_end
        ctx.seq_batch += 1
        batch = Batch(
            batch_number=f"B{completed_at:%Y%m%d}-{ctx.seq_batch:03d}",
            production_order_id=order.id,
            resource_id=resource.id,
            planned_quantity=planned_qty,
            actual_quantity=actual_qty,
            yield_percent=(yield_pct * 100).quantize(Decimal("0.01")),
            status=BatchStatus.COMPLETED.value,
            completed_at=completed_at,
        )
        ctx.session.add(batch)
        batches.append(batch)
        ctx.summary.batches += 1
        ctx.session.flush()  # populate batch.id before adding dependent records

        if recipe is not None:
            scale = actual_qty / STANDARD_BATCH_LITERS
            for component in recipe.components:
                ctx.session.add(
                    MaterialConsumption(
                        batch_id=batch.id,
                        material_id=component.component_material_id,
                        quantity=(component.quantity * scale).quantize(Decimal("0.001")),
                        unit=component.unit,
                        consumption_time=completed_at,
                    )
                )
                ctx.summary.consumptions += 1
            for index, operation in enumerate(recipe.operations):
                ctx.session.add(
                    ProductionConfirmation(
                        batch_id=batch.id,
                        operation=operation.operation_description,
                        quantity=actual_qty,
                        unit="L",
                        confirmation_time=completed_at,
                        is_final=(index == len(recipe.operations) - 1),
                    )
                )
                ctx.summary.confirmations += 1

    order.actual_quantity = total_actual.quantize(Decimal("0.001"))
    ctx.session.flush()
    return batches
