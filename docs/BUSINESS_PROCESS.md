# Business Process

End-to-end production → quality → cost flow, mirroring a real ERP.

> Synthetic data — for educational and simulation purposes only.

## Master data

1. **Materials** — raw materials, packaging and finished products (base unit,
   plant, type).
2. **Recipes** — a BOM (components with quantities/units) and a routing
   (operations with work centers and standard times).
3. **Resources** — machines/lines assigned to work centers.

## Production flow (PP-PI → QM → CO)

```
Production Order (CREATED)
        │
        ▼
Production Event
        │
  ┌─────┴──────────┬──────────┐
  ▼                ▼          ▼
Batch           Inspection   Cost
(PP-PI)          (QM)        (CO)
        │                │
        └────────────────┴────→ Analytics
```

1. **Create order** — validates an active material and a matching recipe.
2. **Create batch** — auto-triggers a pending **Quality Inspection** (QM gate).
3. **Execute/complete order** — transitions `CREATED → RELEASED → IN_PROCESS →
   COMPLETED` (state machine enforced); auto-creates a **Cost Record** (CO).
4. **Record inspection result** — `PENDING → IN_PROGRESS → PASSED/FAILED`.
5. **Quality failure impact** — a `FAILED` inspection applies a rework cost
   factor (+8%) to the order's actual costs (QM → CO).
6. **Non-conformities** — recorded against a failed inspection with severity
   and disposition (REWORK/SCRAP/...).
7. **Analytics** — KPIs (volume, OEE, pass rate, costs) aggregated for the
   dashboard, including a monthly trend.

## Scenarios

- **Normal** — yield ~96%, quality pass rate ~97%, cost variance ~+2%.
- **Crisis (cause and effect)** — increased downtime → lower yield → quality
  deviation → rework → higher cost (visible in the monthly trend).

## Roles

| Role | Access |
|------|--------|
| viewer | read-only |
| operator | write (create/update) |
| admin | write + delete + user management |
