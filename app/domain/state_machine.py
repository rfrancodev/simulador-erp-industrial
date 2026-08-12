"""Domain state machines for Production Order and Quality Inspection.

Enforces legal status transitions so business flows cannot skip mandatory
steps (M-14, M-15). The transition maps are the single source of truth and are
used by the service layer; the API layer never mutates status directly.
"""

from app.core.exceptions import InvalidStateTransitionError
from app.domain.production.recipe import ProductionOrderStatus
from app.domain.quality.inspection import InspectionStatus

PRODUCTION_ORDER_TRANSITIONS: dict[ProductionOrderStatus, set[ProductionOrderStatus]] = {
    ProductionOrderStatus.CREATED: {ProductionOrderStatus.RELEASED},
    ProductionOrderStatus.RELEASED: {ProductionOrderStatus.IN_PROCESS},
    ProductionOrderStatus.IN_PROCESS: {ProductionOrderStatus.COMPLETED, ProductionOrderStatus.PARTIAL},
    ProductionOrderStatus.PARTIAL: {ProductionOrderStatus.COMPLETED},
    ProductionOrderStatus.COMPLETED: {ProductionOrderStatus.CLOSED},
    ProductionOrderStatus.CLOSED: {ProductionOrderStatus.DELIVERED},
}

INSPECTION_TRANSITIONS: dict[InspectionStatus, set[InspectionStatus]] = {
    InspectionStatus.PENDING: {InspectionStatus.IN_PROGRESS},
    InspectionStatus.IN_PROGRESS: {InspectionStatus.PASSED, InspectionStatus.FAILED},
    InspectionStatus.FAILED: {InspectionStatus.REWORK, InspectionStatus.SCRAP},
    InspectionStatus.REWORK: {InspectionStatus.IN_PROGRESS},
}


def validate_transition(
    transitions: dict,
    current,
    target,
    entity: str,
) -> None:
    """Raise :class:`InvalidStateTransitionError` if ``target`` is unreachable."""
    allowed = transitions.get(current, set())
    if target not in allowed:
        raise InvalidStateTransitionError(
            entity=entity,
            current=current,
            target=target,
            allowed=allowed,
        )
