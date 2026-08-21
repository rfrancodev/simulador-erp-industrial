"""Analytics service — aggregates PP-PI, QM and CO data for the dashboard."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.domain.entities import (
    Batch,
    CostRecord,
    Material,
    NonConformity,
    ProductionOrder,
    ProductionResource,
    ProductionRecipe,
    QualityInspection,
)


class AnalyticsService:
    def __init__(self, session: Session):
        self._session = session

    # ── Executive KPIs ───────────────────────────────────────────────────

    def executive_kpis(self) -> dict:
        return {
            "production": self._production_kpi(),
            "quality": self._quality_kpi(),
            "cost": self._cost_kpi(),
            "orders": self._orders_kpi(),
            "oee": self.oee(),
            "machine_utilization": self.machine_utilization(),
            "cost_per_liter": self.cost_per_liter(),
            "quality_cost": self.quality_cost(),
        }

    def _production_kpi(self) -> dict:
        total_qty = self._session.scalar(
            select(func.coalesce(func.sum(Batch.actual_quantity), 0))
            .join(ProductionOrder, Batch.production_order_id == ProductionOrder.id)
            .where(ProductionOrder.status == "COMPLETED")
        ) or Decimal("0")

        active_orders = self._session.scalar(
            select(func.count(ProductionOrder.id)).where(
                ProductionOrder.status.in_(["CREATED", "RELEASED", "IN_PROCESS"])
            )
        ) or 0

        return {
            "total_volume_liters": float(total_qty),
            "active_orders": active_orders,
        }

    def _quality_kpi(self) -> dict:
        total = self._session.scalar(
            select(func.count(QualityInspection.id))
        ) or 0
        passed = self._session.scalar(
            select(func.count(QualityInspection.id)).where(
                QualityInspection.inspection_status == "PASSED"
            )
        ) or 0
        failed = self._session.scalar(
            select(func.count(QualityInspection.id)).where(
                QualityInspection.inspection_status == "FAILED"
            )
        ) or 0
        nc_count = self._session.scalar(
            select(func.count(NonConformity.id))
        ) or 0

        pass_rate = (passed / total * 100) if total > 0 else 0.0
        scrap_rate = (failed / total * 100) if total > 0 else 0.0

        return {
            "total_inspections": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(pass_rate, 1),
            "scrap_rate": round(scrap_rate, 1),
            "non_conformities": nc_count,
        }

    def _cost_kpi(self) -> dict:
        total_planned = self._session.scalar(
            select(func.coalesce(func.sum(CostRecord.planned_total_cost), 0))
        ) or Decimal("0")
        total_actual = self._session.scalar(
            select(func.coalesce(func.sum(CostRecord.actual_total_cost), 0))
        ) or Decimal("0")

        variance = total_actual - total_planned
        variance_pct = (float(variance / total_planned) * 100) if total_planned > 0 else 0.0

        records_with_actual = self._session.scalar(
            select(func.count(CostRecord.id)).where(CostRecord.actual_total_cost.isnot(None))
        ) or 0

        return {
            "total_planned_cost": float(total_planned),
            "total_actual_cost": float(total_actual),
            "variance": float(variance),
            "variance_percent": round(variance_pct, 1),
            "records_with_actual": records_with_actual,
        }

    def _orders_kpi(self) -> dict:
        total = self._session.scalar(select(func.count(ProductionOrder.id))) or 0
        completed = self._session.scalar(
            select(func.count(ProductionOrder.id)).where(ProductionOrder.status == "COMPLETED")
        ) or 0

        return {
            "total_orders": total,
            "completed_orders": completed,
            "completion_rate": round(completed / total * 100, 1) if total > 0 else 0.0,
        }

    # ── Advanced indicators ───────────────────────────────────────────────

    def oee(self) -> dict:
        """Overall Equipment Effectiveness = availability x performance x quality.

        Availability is derived from the planned vs actual duration of completed
        orders; performance from the batch yield; quality from the pass rate.
        """
        # Performance = yield (actual / planned) across batches.
        total_actual = self._session.scalar(
            select(func.coalesce(func.sum(Batch.actual_quantity), 0))
        ) or Decimal("0")
        total_planned = self._session.scalar(
            select(func.coalesce(func.sum(Batch.planned_quantity), 0))
        ) or Decimal("0")
        performance = float(total_actual / total_planned) if total_planned > 0 else 0.0

        # Quality = pass rate.
        total_inspections = self._session.scalar(
            select(func.count(QualityInspection.id))
        ) or 0
        passed = self._session.scalar(
            select(func.count(QualityInspection.id)).where(
                QualityInspection.inspection_status == "PASSED"
            )
        ) or 0
        quality = (passed / total_inspections) if total_inspections > 0 else 0.0

        # Availability = mean(planned_duration / actual_duration) of completed orders.
        orders = list(self._session.execute(
            select(ProductionOrder).where(
                ProductionOrder.status == "COMPLETED",
                ProductionOrder.actual_start.isnot(None),
                ProductionOrder.actual_end.isnot(None),
            )
        ).scalars().all())
        ratios = []
        for order in orders:
            planned = (order.planned_end - order.planned_start).total_seconds()
            actual = (order.actual_end - order.actual_start).total_seconds()
            if planned > 0 and actual > 0:
                ratios.append(min(1.0, planned / actual))
        availability = (sum(ratios) / len(ratios)) if ratios else 0.0

        oee = min(1.0, availability * performance * quality)
        return {
            "oee": round(oee * 100, 1),
            "availability": round(availability * 100, 1),
            "performance": round(performance * 100, 1),
            "quality": round(quality * 100, 1),
        }

    def machine_utilization(self) -> float:
        """Share of production resources that produced at least one batch (%)."""
        total = self._session.scalar(select(func.count(ProductionResource.id))) or 0
        used = self._session.scalar(
            select(func.count(func.distinct(Batch.resource_id)))
        ) or 0
        return round(used / total * 100, 1) if total > 0 else 0.0

    def cost_per_liter(self) -> float:
        """Actual cost (planned fallback) per produced liter."""
        total_cost = self._session.scalar(
            select(func.coalesce(func.sum(CostRecord.actual_total_cost), 0))
        ) or Decimal("0")
        total_volume = self._session.scalar(
            select(func.coalesce(func.sum(Batch.actual_quantity), 0))
        ) or Decimal("0")
        if total_volume > 0:
            return round(float(total_cost / total_volume), 2)
        return 0.0

    def quality_cost(self) -> float:
        """Cost variance attributable to orders with a failed inspection (rework/scrap)."""
        failed_order_ids = (
            select(Batch.production_order_id)
            .join(QualityInspection, QualityInspection.batch_id == Batch.id)
            .where(QualityInspection.inspection_status == "FAILED")
            .distinct()
        )
        variance = self._session.scalar(
            select(func.coalesce(func.sum(
                func.coalesce(CostRecord.actual_total_cost, CostRecord.planned_total_cost)
                - CostRecord.planned_total_cost
            ), 0)).where(CostRecord.production_order_id.in_(failed_order_ids))
        ) or Decimal("0")
        return round(float(variance), 2)

    # ── Module stats ──────────────────────────────────────────────────────

    def production_stats(
        self,
        page: int = 1,
        per_page: int = 10,
        order: Optional[str] = None,
        status: Optional[str] = None,
        planned_start_from: Optional[date] = None,
        planned_start_to: Optional[date] = None,
        planned_min: Optional[Decimal] = None,
        planned_max: Optional[Decimal] = None,
        actual_min: Optional[Decimal] = None,
        actual_max: Optional[Decimal] = None,
    ) -> dict:
        """Production module stats with server-side pagination and filters.

        Orders are ordered by ``planned_start`` (the production time dimension)
        so the history can be navigated month by month; ``created_at`` is not
        used here because it reflects the simulation run time, not production.
        """
        materials_count = self._session.scalar(select(func.count(Material.id))) or 0
        recipes_count = self._session.scalar(select(func.count(ProductionRecipe.id))) or 0
        resources_count = self._session.scalar(select(func.count(ProductionResource.id))) or 0

        conditions: list = []
        if order:
            conditions.append(ProductionOrder.order_number.ilike(f"%{order}%"))
        if status:
            conditions.append(ProductionOrder.status == status)
        if planned_start_from is not None:
            start_dt = datetime.combine(planned_start_from, datetime.min.time()).replace(tzinfo=UTC)
            conditions.append(ProductionOrder.planned_start >= start_dt)
        if planned_start_to is not None:
            end_dt = (
                datetime.combine(planned_start_to, datetime.min.time()).replace(tzinfo=UTC)
                + timedelta(days=1)
            )
            conditions.append(ProductionOrder.planned_start < end_dt)
        if planned_min is not None:
            conditions.append(ProductionOrder.planned_quantity >= planned_min)
        if planned_max is not None:
            conditions.append(ProductionOrder.planned_quantity <= planned_max)
        if actual_min is not None:
            conditions.append(ProductionOrder.actual_quantity >= actual_min)
        if actual_max is not None:
            conditions.append(ProductionOrder.actual_quantity <= actual_max)

        total_orders = self._session.scalar(
            select(func.count(ProductionOrder.id)).where(*conditions)
        ) or 0
        total_pages = max(1, math.ceil(total_orders / per_page))
        page = min(max(1, page), total_pages)
        offset = (page - 1) * per_page

        recent_orders = list(
            self._session.execute(
                select(ProductionOrder)
                .where(*conditions)
                .order_by(ProductionOrder.planned_start.desc(), ProductionOrder.id.desc())
                .offset(offset)
                .limit(per_page)
            ).scalars().all()
        )

        return {
            "materials_count": materials_count,
            "recipes_count": recipes_count,
            "resources_count": resources_count,
            "recent_orders": [
                {
                    "id": o.id,
                    "order_number": o.order_number,
                    "status": o.status,
                    "planned_quantity": float(o.planned_quantity),
                    "actual_quantity": float(o.actual_quantity) if o.actual_quantity else None,
                    "planned_start": o.planned_start.isoformat() if o.planned_start else None,
                    "planned_end": o.planned_end.isoformat() if o.planned_end else None,
                }
                for o in recent_orders
            ],
            "total_orders": total_orders,
            "total_pages": total_pages,
            "page": page,
            "per_page": per_page,
        }

    def quality_stats(self) -> dict:
        pending = self._session.scalar(
            select(func.count(QualityInspection.id)).where(
                QualityInspection.inspection_status == "PENDING"
            )
        ) or 0

        inspections = list(
            self._session.execute(
                select(QualityInspection)
                .order_by(QualityInspection.inspection_date.desc())
                .limit(10)
            ).scalars().all()
        )

        return {
            "pending_inspections": pending,
            "recent_inspections": [
                {
                    "id": i.id,
                    "inspection_lot": i.inspection_lot,
                    "status": i.inspection_status,
                    "pH": float(i.pH) if i.pH else None,
                    "alcohol_percent": float(i.alcohol_percent) if i.alcohol_percent else None,
                }
                for i in inspections
            ],
        }

    def cost_stats(self) -> dict:
        cost_by_material = list(
            self._session.execute(
                select(
                    Material.material_name,
                    func.coalesce(func.sum(CostRecord.planned_total_cost), 0).label("planned"),
                    func.coalesce(func.sum(CostRecord.actual_total_cost), Decimal("0")).label("actual"),
                )
                .join(ProductionOrder, CostRecord.production_order_id == ProductionOrder.id)
                .join(Material, ProductionOrder.material_id == Material.id)
                .group_by(Material.material_name)
                .order_by(func.sum(CostRecord.planned_total_cost).desc())
                .limit(10)
            ).all()
        )

        return {
            "cost_by_material": [
                {"material": name, "planned": float(p or 0), "actual": float(a or 0)}
                for name, p, a in cost_by_material
            ],
        }

    # ── Modal datasets (loaded on demand) ─────────────────────────────────

    def materials(self) -> list[dict]:
        """List materials for the clickable KPI modal."""
        rows = list(
            self._session.execute(
                select(Material).order_by(Material.material_code)
            ).scalars().all()
        )
        return [
            {
                "code": m.material_code,
                "name": m.material_name,
                "unit": m.base_unit,
                "type": m.material_type,
                "plant": m.plant,
                "active": m.is_active,
            }
            for m in rows
        ]

    def recipes(self) -> list[dict]:
        """List recipes (with product name) for the clickable KPI modal."""
        rows = list(
            self._session.execute(
                select(ProductionRecipe, Material.material_name)
                .join(Material, ProductionRecipe.material_id == Material.id)
                .order_by(ProductionRecipe.recipe_code)
            ).all()
        )
        return [
            {
                "code": r.recipe_code,
                "product": name,
                "version": r.version,
                "active": r.is_active,
            }
            for r, name in rows
        ]

    def resources(self) -> list[dict]:
        """List production resources for the clickable KPI modal."""
        rows = list(
            self._session.execute(
                select(ProductionResource).order_by(ProductionResource.resource_code)
            ).scalars().all()
        )
        return [
            {
                "code": r.resource_code,
                "name": r.resource_name,
                "type": r.resource_type,
                "work_center": r.work_center,
                "available": r.is_available,
            }
            for r in rows
        ]

    def non_conformities(self) -> list[dict]:
        """List non-conformities linked to their order/inspection for the modal."""
        rows = list(
            self._session.execute(
                select(
                    NonConformity,
                    ProductionOrder.order_number,
                    QualityInspection.inspection_lot,
                )
                .join(QualityInspection, NonConformity.inspection_id == QualityInspection.id)
                .join(Batch, QualityInspection.batch_id == Batch.id)
                .join(ProductionOrder, Batch.production_order_id == ProductionOrder.id)
                .order_by(NonConformity.created_at.desc(), NonConformity.id.desc())
            ).all()
        )
        return [
            {
                "order_number": order_number,
                "inspection_lot": inspection_lot,
                "defect_code": nc.defect_code,
                "defect_type": nc.defect_type,
                "description": nc.description,
                "severity": nc.severity,
                "disposition": nc.disposition,
                "date": nc.created_at.strftime("%Y-%m-%d") if nc.created_at else None,
            }
            for nc, order_number, inspection_lot in rows
        ]

    def pending_inspections(self) -> list[dict]:
        """List pending inspections linked to their order/batch for the modal."""
        rows = list(
            self._session.execute(
                select(
                    QualityInspection,
                    ProductionOrder.order_number,
                    Batch.batch_number,
                )
                .join(Batch, QualityInspection.batch_id == Batch.id)
                .join(ProductionOrder, Batch.production_order_id == ProductionOrder.id)
                .where(QualityInspection.inspection_status == "PENDING")
                .order_by(QualityInspection.inspection_date.desc(), QualityInspection.id.desc())
            ).all()
        )
        return [
            {
                "order_number": order_number,
                "batch_number": batch_number,
                "inspection_lot": i.inspection_lot,
                "date": i.inspection_date.strftime("%Y-%m-%d") if i.inspection_date else None,
                "status": i.inspection_status,
            }
            for i, order_number, batch_number in rows
        ]

    # ── Order 360° ────────────────────────────────────────────────────────

    def order_360(self, order_number: str) -> Optional[dict]:
        order = self._session.execute(
            select(ProductionOrder)
            .where(ProductionOrder.order_number == order_number)
        ).scalar_one_or_none()

        if order is None:
            return None

        material = self._session.get(Material, order.material_id)
        recipe = self._session.execute(
            select(ProductionRecipe)
            .options(
                joinedload(ProductionRecipe.components),
                joinedload(ProductionRecipe.operations),
            )
            .where(ProductionRecipe.id == order.recipe_id)
        ).unique().scalar_one_or_none()
        cost = self._session.execute(
            select(CostRecord).where(CostRecord.production_order_id == order.id)
        ).scalar_one_or_none()

        batches = list(
            self._session.execute(
                select(Batch).where(Batch.production_order_id == order.id)
            ).scalars().all()
        )

        inspections = []
        for batch in batches:
            insp = self._session.execute(
                select(QualityInspection).where(QualityInspection.batch_id == batch.id)
            ).scalar_one_or_none()
            if insp:
                inspections.append(insp)

        return {
            "order": {
                "id": order.id,
                "order_number": order.order_number,
                "status": order.status,
                "planned_quantity": float(order.planned_quantity),
                "actual_quantity": float(order.actual_quantity) if order.actual_quantity else None,
                "planned_start": order.planned_start.isoformat() if order.planned_start else None,
                "planned_end": order.planned_end.isoformat() if order.planned_end else None,
                "yield_percent": (
                    round(float(order.actual_quantity) / float(order.planned_quantity) * 100, 1)
                    if order.actual_quantity and order.planned_quantity
                    else None
                ),
            },
            "material": {
                "code": material.material_code if material else None,
                "name": material.material_name if material else None,
            },
            "recipe": {
                "code": recipe.recipe_code if recipe else None,
                "version": recipe.version if recipe else None,
            },
            "batches": [
                {
                    "batch_number": b.batch_number,
                    "status": b.status,
                    "planned_quantity": float(b.planned_quantity),
                    "actual_quantity": float(b.actual_quantity) if b.actual_quantity else None,
                }
                for b in batches
            ],
            "quality": [
                {
                    "inspection_lot": i.inspection_lot,
                    "status": i.inspection_status,
                    "pH": float(i.pH) if i.pH else None,
                    "alcohol_percent": float(i.alcohol_percent) if i.alcohol_percent else None,
                }
                for i in inspections
            ],
            "cost": {
                "planned_total": float(cost.planned_total_cost) if cost else None,
                "actual_total": (
                    float(cost.actual_total_cost)
                    if cost and cost.actual_total_cost is not None
                    else None
                ),
                "variance": float(cost.variance) if cost and cost.variance else None,
                "variance_percent": float(cost.variance_percent) if cost and cost.variance_percent else None,
            }
            if cost else None,
        }

    # ── Trend data (for Plotly charts) ────────────────────────────────────

    def order_status_distribution(self) -> list[dict]:
        rows = list(self._session.execute(
            select(
                ProductionOrder.status,
                func.count(ProductionOrder.id),
            ).group_by(ProductionOrder.status)
        ).all())
        return [{"status": r[0], "count": r[1]} for r in rows]

    def inspection_status_distribution(self) -> list[dict]:
        rows = list(self._session.execute(
            select(
                QualityInspection.inspection_status,
                func.count(QualityInspection.id),
            ).group_by(QualityInspection.inspection_status)
        ).all())
        return [{"status": r[0], "count": r[1]} for r in rows]

    def cost_variance_by_order(self) -> list[dict]:
        rows = list(self._session.execute(
            select(
                ProductionOrder.order_number,
                CostRecord.planned_total_cost,
                CostRecord.actual_total_cost,
            )
            .join(CostRecord, CostRecord.production_order_id == ProductionOrder.id)
            .where(CostRecord.actual_total_cost.isnot(None))
            .order_by(CostRecord.planned_total_cost.desc())
            .limit(15)
        ).all())
        return [
            {
                "order": r[0],
                "planned": float(r[1] or 0),
                "actual": float(r[2] or 0),
            }
            for r in rows
        ]

    # ── Monthly trend ─────────────────────────────────────────────────────

    def monthly_trend(self) -> list[dict]:
        """Aggregate PP-PI / QM / CO metrics per calendar month.

        Returns a list ordered by month (``YYYY-MM``) with order count, produced
        volume, quality pass rate and planned/actual cost — enabling trend
        analysis across the simulated period (including a crisis window).
        """
        orders = list(
            self._session.execute(
                select(ProductionOrder)
                .where(ProductionOrder.planned_start.isnot(None))
                .order_by(ProductionOrder.planned_start)
            ).scalars().all()
        )

        cost_by_order = {
            c.production_order_id: c
            for c in self._session.execute(select(CostRecord)).scalars().all()
        }

        inspection_status_by_order: dict[int, list[str]] = defaultdict(list)
        batch_rows = self._session.execute(
            select(Batch.production_order_id, QualityInspection.inspection_status)
            .join(QualityInspection, QualityInspection.batch_id == Batch.id, isouter=True)
        ).all()
        for order_id, status in batch_rows:
            if status is not None:
                inspection_status_by_order[order_id].append(status)

        buckets: dict[str, dict] = {}
        for order in orders:
            key = order.planned_start.strftime("%Y-%m")
            bucket = buckets.setdefault(key, {
                "month": key,
                "orders": 0,
                "volume_liters": 0.0,
                "inspected": 0,
                "passed": 0,
                "planned_cost": 0.0,
                "actual_cost": 0.0,
            })
            bucket["orders"] += 1
            volume = order.actual_quantity if order.actual_quantity is not None else order.planned_quantity
            bucket["volume_liters"] += float(volume)
            cost = cost_by_order.get(order.id)
            if cost is not None:
                bucket["planned_cost"] += float(cost.planned_total_cost)
                if cost.actual_total_cost is not None:
                    bucket["actual_cost"] += float(cost.actual_total_cost)
            for status in inspection_status_by_order.get(order.id, []):
                bucket["inspected"] += 1
                if status == "PASSED":
                    bucket["passed"] += 1

        result = []
        for key in sorted(buckets):
            bucket = buckets[key]
            pass_rate = (
                bucket["passed"] / bucket["inspected"] * 100
                if bucket["inspected"]
                else 0.0
            )
            result.append({
                "month": key,
                "orders": bucket["orders"],
                "volume_liters": round(bucket["volume_liters"], 1),
                "pass_rate": round(pass_rate, 1),
                "planned_cost": round(bucket["planned_cost"], 2),
                "actual_cost": round(bucket["actual_cost"], 2),
            })
        return result
