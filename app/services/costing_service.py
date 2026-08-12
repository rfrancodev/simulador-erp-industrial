"""Controlling service — CO business rules.

Owns the transaction boundary: methods commit on success and roll back on
failure, so multi-entity operations stay atomic (M-05). Database exceptions are
translated into domain errors before propagating to the API layer (L-03).
"""

from __future__ import annotations

from logging import getLogger

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateEntityError, EntityNotFoundError
from app.domain.costing.cost import (
    CostRecordCreate,
    CostRecordUpdate,
    CostSummary,
)
from app.domain.entities import CostRecord
from app.repositories.costing_repository import CostRecordRepository
from app.repositories.production_repository import ProductionOrderRepository

logger = getLogger(__name__)


class CostingService:
    def __init__(self, session: Session):
        self._session = session
        self.records = CostRecordRepository(session)
        self.orders = ProductionOrderRepository(session)

    def create_cost_record(self, data: CostRecordCreate) -> CostRecord:
        if self.orders.get_by_id(data.production_order_id) is None:
            raise EntityNotFoundError("ProductionOrder", data.production_order_id)

        try:
            record = self.records.create_for_order(data.production_order_id, data)
            self._session.commit()
            logger.info(
                "Cost record for production order %s created",
                data.production_order_id,
            )
            return record
        except IntegrityError:
            self._session.rollback()
            raise DuplicateEntityError("CostRecord", data.production_order_id) from None

    def list_cost_records(self, skip: int = 0, limit: int = 100) -> list[CostRecord]:
        return self.records.get_all(skip, limit)

    def get_cost_record(self, id: int) -> CostRecord:
        record = self.records.get_by_id(id)
        if record is None:
            raise EntityNotFoundError("CostRecord", id)
        return record

    def get_cost_record_by_order(self, order_id: int) -> CostRecord:
        if self.orders.get_by_id(order_id) is None:
            raise EntityNotFoundError("ProductionOrder", order_id)
        record = self.records.get_by_order(order_id)
        if record is None:
            raise EntityNotFoundError("CostRecord", order_id)
        return record

    def update_actual_costs(self, id: int, data: CostRecordUpdate) -> CostRecord:
        record = self.records.get_by_id(id)
        if record is None:
            raise EntityNotFoundError("CostRecord", id)

        updated = self.records.update_actual(id, data)
        self._session.commit()
        logger.info("Cost record %s actual costs updated", id)
        return updated

    def get_summary(self, id: int) -> CostSummary:
        record = self.get_cost_record(id)
        return CostSummary(
            planned_total=record.planned_total_cost,
            actual_total=record.actual_total_cost,
            variance=record.variance,
            variance_percent=record.variance_percent,
        )