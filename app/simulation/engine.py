"""Simulation engine — orchestrates the PP-PI → QM → CO flow.

The engine generates a full year (or more) of synthetic industrial data:
master data (materials, recipes, resources), production orders, batches,
quality inspections and cost records — respecting the cross-module integration
documented in ``plano/08-integracao-eventos.md`` (a quality failure raises cost).

Synthetic data — for educational and simulation purposes only.
"""

from __future__ import annotations

import logging
import random
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.domain.quality.inspection import InspectionStatus
from app.simulation import cost_generator, production_generator, quality_generator
from app.simulation.config import (
    MonthParams,
    SimulationConfig,
    SimulationContext,
    SimulationSummary,
    add_months,
)

logger = logging.getLogger(__name__)


class SimulationEngine:
    def __init__(self, session: Session, config: SimulationConfig | None = None):
        self.session = session
        self.config = config or SimulationConfig()
        self.rng = random.Random(self.config.seed)

    def run(self) -> SimulationSummary:
        """Generate all synthetic data and return a summary of record counts."""
        ctx = SimulationContext(
            session=self.session,
            rng=self.rng,
            config=self.config,
        )
        production_generator.generate_master_data(ctx)
        self.session.commit()  # persist master data even when months == 0
        alcohol_by_material = {
            ctx.materials[code].id: meta["alcohol_target"]
            for code, meta in ctx.product_meta.items()
        }

        base = datetime(2026, 1, 1, tzinfo=UTC)
        for month_index in range(self.config.months):
            params = self._month_params(month_index)
            month_start = add_months(base, month_index)
            orders = production_generator.generate_month_orders(ctx, month_start, params)
            for order in orders:
                batches = production_generator.generate_batches(ctx, order, params)
                quality_failed = False
                for batch in batches:
                    inspection = quality_generator.generate_inspection(
                        ctx, batch, alcohol_by_material[order.material_id], params
                    )
                    if inspection.inspection_status == InspectionStatus.FAILED.value:
                        quality_failed = True
                cost_generator.generate_cost_record(ctx, order, quality_failed, params)
            self.session.commit()
            logger.info(
                "Simulation month %s/%s done: %s orders, %s batches",
                month_index + 1,
                self.config.months,
                len(orders),
                ctx.summary.batches,
            )

        return ctx.summary

    def _month_params(self, month_index: int) -> MonthParams:
        """Compute effective parameters, degrading conditions during a crisis."""
        c = self.config
        normal = MonthParams(
            failure_rate=c.production_failure_rate,
            yield_mean=c.yield_mean,
            inspection_failure_rate=c.inspection_failure_rate,
            downtime_probability=c.downtime_probability,
            cost_variance=c.cost_variance,
        )
        if c.scenario != "crisis":
            return normal

        total = max(c.months, 1)
        crisis_start = total // 3
        crisis_end = total * 2 // 3
        if crisis_start <= month_index < crisis_end:
            # Cause and effect: more downtime → lower yield → quality deviation →
            # rework → higher cost.
            return MonthParams(
                failure_rate=min(c.production_failure_rate * 2.5, 0.25),
                yield_mean=max(c.yield_mean - 0.06, 0.75),
                inspection_failure_rate=min(c.inspection_failure_rate * 3.0, 0.30),
                downtime_probability=min(c.downtime_probability * 4.0, 0.40),
                cost_variance=c.cost_variance + 0.06,
            )
        return normal
