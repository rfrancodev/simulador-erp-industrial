# Architecture

Industrial ERP Simulator — technical architecture.

> Inspired by SAP S/4HANA concepts. Not an SAP implementation. All industrial
> data is **synthetic** (educational/simulation purposes).

## Overview

A Python-first platform simulating three integrated ERP modules:

| Module | Responsibility |
|--------|----------------|
| **PP-PI** | Production Planning — materials, recipes (BOM + routing), orders, batches, resources, confirmations, consumptions |
| **QM** | Quality Management — inspections, non-conformities, rework/scrap |
| **CO** | Controlling — planned vs actual costs, variance |

The core value is the relationship **operation → quality → money**.

## Layers

```
app/
├── api/            # FastAPI routers (thin controllers)
├── domain/         # SQLAlchemy entities + Pydantic schemas + state machines
├── services/       # business logic + transaction boundaries
├── repositories/   # data access (flush-only; services commit)
├── simulation/     # synthetic data engine
├── analytics/      # dashboard aggregations
├── security/       # JWT, password hashing, RBAC
├── core/           # exceptions, logging, event bus
└── middleware/     # rate limiting
```

- **API → Service → Repository → DB** (no business logic in routers)
- Repositories `flush()`; services own `commit()`/`rollback()` (atomicity, M-05)
- Domain errors translated to HTTP codes (404/409/422/400) in `main.py`

## Cross-module integration (event-driven)

An in-process `EventBus` (`app/core/events.py`) decouples modules. Services
publish events; integration handlers react in the same transaction:

| Event | Handler |
|-------|---------|
| `batch.created` | auto-create a pending Quality Inspection (QM gate) |
| `order.completed` | auto-create a planned Cost Record (CO) |
| `inspection.failed` | apply a rework cost factor to the order's Cost Record (QM → CO) |

Handlers are idempotent and use repositories (flush-only); the publisher commits.

## State machines

`app/domain/state_machine.py` defines legal transitions, enforced at the
service layer:

- **ProductionOrder:** `CREATED → RELEASED → IN_PROCESS → COMPLETED/PARTIAL → CLOSED → DELIVERED`
- **QualityInspection:** `PENDING → IN_PROGRESS → PASSED/FAILED → REWORK/SCRAP`

Invalid transitions raise `InvalidStateTransitionError` (HTTP 409).

## Security

- **JWT** (HS256) authentication + **RBAC** by HTTP method
  (viewer = read, operator = write, admin = delete)
- PBKDF2-SHA256 password hashing (600k iterations, per-user salt)
- Account lockout after 5 failed attempts (15 min)
- In-memory sliding-window rate limiter (per IP)
- All `/api/*` routers protected; HTML dashboard pages are public (read-only)

## Persistence

- SQLAlchemy 2.0 ORM + Alembic migrations
- PostgreSQL (production) / SQLite (tests, in-memory)
- CHECK constraints enforce enums and cost-total invariants at the DB level

## Dashboard

Server-side Jinja2 templates + Plotly.js (CDN). Python-first: aggregations in
`AnalyticsService` (SQLAlchemy), no SPA framework.

## Deployment

See `RUNBOOK.md` and `docker-compose.prod.yml`.
