"""Repository for CO — Controlling / Costing domain."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.costing.cost import CostRecordCreate, CostRecordUpdate
from app.domain.entities import CostRecord
from app.repositories.base import BaseRepository


class CostRecordRepository(BaseRepository[CostRecord]):
    def __init__(self, session: Session):
        super().__init__(CostRecord, session)

    def get_by_order(self, order_id: int) -> CostRecord | None:
        stmt = select(CostRecord).where(CostRecord.production_order_id == order_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def create_for_order(self, order_id: int, data: CostRecordCreate) -> CostRecord:
        cost_record = CostRecord(
            production_order_id=order_id,
            planned_material_cost=data.planned_material_cost,
            planned_labor_cost=data.planned_labor_cost,
            planned_machine_cost=data.planned_machine_cost,
            planned_energy_cost=data.planned_energy_cost,
            planned_total_cost=(
                data.planned_material_cost
                + data.planned_labor_cost
                + data.planned_machine_cost
                + data.planned_energy_cost
            ),
        )
        return self.add(cost_record)

    def update_actual(self, id: int, data: CostRecordUpdate) -> CostRecord | None:
        record = self.get_by_id(id)
        if record is None:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(record, key, value)
        record.actual_total_cost = (
            (record.actual_material_cost or Decimal("0"))
            + (record.actual_labor_cost or Decimal("0"))
            + (record.actual_machine_cost or Decimal("0"))
            + (record.actual_energy_cost or Decimal("0"))
        )
        self._session.flush()
        self._session.refresh(record)
        return record
