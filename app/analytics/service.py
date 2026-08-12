"""Analytics service — aggregates PP-PI, QM and CO data for the dashboard."""

from __future__ import annotations

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

    # ── Module stats ──────────────────────────────────────────────────────

    def production_stats(self) -> dict:
        materials_count = self._session.scalar(select(func.count(Material.id))) or 0
        recipes_count = self._session.scalar(select(func.count(ProductionRecipe.id))) or 0
        resources_count = self._session.scalar(select(func.count(ProductionResource.id))) or 0

        recent_orders = list(
            self._session.execute(
                select(ProductionOrder)
                .order_by(ProductionOrder.created_at.desc())
                .limit(10)
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
                "actual_total": float(cost.actual_total_cost) if cost else None,
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
