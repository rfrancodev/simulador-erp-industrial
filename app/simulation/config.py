"""Simulation configuration and shared data holders.

The simulation engine is isolated from the web application: it reads synthetic
data parameters from environment variables (``SIM_*``) and writes entities via
the SQLAlchemy session directly (not through the API service layer).

Synthetic data — for educational and simulation purposes only.
"""

from __future__ import annotations

import calendar
import math
import os
import random
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy.orm import Session

from app.domain.entities import Material, ProductionRecipe, ProductionResource

# Standard recipe batch size (liters) used to scale BOM quantities to an order.
STANDARD_BATCH_LITERS = Decimal("10000")


def to_decimal(value: float, places: int = 2) -> Decimal:
    """Round a *finite* float to a fixed number of decimal places (Decimal)."""
    if not math.isfinite(value):
        raise ValueError(f"to_decimal requires a finite number, got {value!r}")
    quantum = Decimal(10) ** -places
    return Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)


def add_months(base, months: int):
    """Return ``base`` shifted forward by ``months`` (calendar-safe, day-clamped)."""
    month_index = base.month - 1 + months
    year = base.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return base.replace(year=year, month=month, day=day)


@dataclass
class SimulationConfig:
    """Parameters that drive the simulation (overridable via env / CLI)."""

    months: int = 12
    seed: Optional[int] = 42
    scenario: str = "normal"  # "normal" | "crisis"
    orders_per_month: int = 15
    max_batches_per_order: int = 3
    production_failure_rate: float = 0.03
    yield_mean: float = 0.96
    inspection_failure_rate: float = 0.04
    downtime_probability: float = 0.05
    cost_variance: float = 0.02

    @classmethod
    def from_env(cls, **overrides) -> "SimulationConfig":
        def _parse(name: str, default: str, cast):
            raw = os.getenv(name, default)
            try:
                return cast(raw)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid {name} value: {raw!r}") from None

        seed_raw = os.getenv("SIM_SEED")
        values = {
            "months": _parse("SIM_MONTHS", "12", int),
            "seed": int(seed_raw) if seed_raw not in (None, "") else None,
            "scenario": os.getenv("SIM_SCENARIO", "normal"),
            "orders_per_month": _parse("SIM_ORDERS_PER_MONTH", "15", int),
            "production_failure_rate": _parse("SIM_FAILURE_RATE", "0.03", float),
            "yield_mean": _parse("SIM_YIELD_MEAN", "0.96", float),
            "inspection_failure_rate": _parse("SIM_INSPECTION_FAILURE_RATE", "0.04", float),
            "downtime_probability": _parse("SIM_DOWNTIME_PROBABILITY", "0.05", float),
        }
        values.update(overrides)
        return cls(**values)


@dataclass
class MonthParams:
    """Effective parameters for a single simulated month (post scenario)."""

    failure_rate: float
    yield_mean: float
    inspection_failure_rate: float
    downtime_probability: float
    cost_variance: float


@dataclass
class SimulationSummary:
    """Counts of generated records, returned by the engine for reporting/tests."""

    materials: int = 0
    recipes: int = 0
    resources: int = 0
    orders: int = 0
    batches: int = 0
    confirmations: int = 0
    consumptions: int = 0
    inspections: int = 0
    non_conformities: int = 0
    cost_records: int = 0

    def total_records(self) -> int:
        return (
            self.materials
            + self.recipes
            + self.resources
            + self.orders
            + self.batches
            + self.confirmations
            + self.consumptions
            + self.inspections
            + self.non_conformities
            + self.cost_records
        )


@dataclass
class SimulationContext:
    """Shared mutable state threaded through the generator functions."""

    session: Session
    rng: random.Random
    config: SimulationConfig
    summary: SimulationSummary = field(default_factory=SimulationSummary)
    materials: dict[str, Material] = field(default_factory=dict)
    recipes: dict[str, ProductionRecipe] = field(default_factory=dict)
    resources: list[ProductionResource] = field(default_factory=list)
    finished_products: list[Material] = field(default_factory=list)
    product_meta: dict[str, dict] = field(default_factory=dict)
    material_code_by_id: dict[int, str] = field(default_factory=dict)
    recipe_by_id: dict[int, ProductionRecipe] = field(default_factory=dict)
    seq_order: int = 0
    seq_batch: int = 0
    seq_inspection: int = 0
    seq_defect: int = 0
