"""In-process event bus for cross-module integration (plano/08-integracao-eventos.md).

A lightweight publish/subscribe mechanism: production services publish domain
events and integration handlers react, wiring PP-PI -> QM -> CO without tight
coupling between modules. Handlers run synchronously in the same transaction as
the publisher (they use repositories that flush; the publisher commits).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

EVENT_BATCH_CREATED = "batch.created"
EVENT_BATCH_COMPLETED = "batch.completed"
EVENT_ORDER_COMPLETED = "order.completed"
EVENT_INSPECTION_FAILED = "inspection.failed"


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable) -> None:
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    def publish(self, event_type: str, **payload) -> None:
        for handler in list(self._handlers[event_type]):
            handler(**payload)


# Shared singleton. Handlers are registered once at application startup
# (see ``app.services.integration.register_integration_handlers``).
event_bus = EventBus()
