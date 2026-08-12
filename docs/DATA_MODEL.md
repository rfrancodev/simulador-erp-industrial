# Data Model

Entities, relationships and key constraints (SQLAlchemy + Alembic).

## Entities

### Auth

| Entity | Fields |
|--------|--------|
| **User** | id, username (unique), password_hash, role (admin/operator/viewer), is_active, failed_attempts, locked_until, created_at |

### PP-PI

| Entity | Fields |
|--------|--------|
| **Material** | id, material_code (unique), material_name, material_type, base_unit, plant, is_active |
| **ProductionRecipe** | id, recipe_code (unique), material_id, version, is_active |
| **RecipeComponent** | id, recipe_id, component_material_id, quantity, unit |
| **RecipeOperation** | id, recipe_id, sequence, work_center, operation_description, standard_time_minutes |
| **ProductionOrder** | id, order_number (unique), material_id, recipe_id, planned/actual quantity, planned/actual start/end, status |
| **ProductionResource** | id, resource_code (unique), resource_name, work_center, resource_type, is_available |
| **Batch** | id, batch_number (unique), production_order_id, resource_id, planned/actual quantity, yield_percent, status, completed_at |
| **ProductionConfirmation** | id, batch_id, operation, quantity, unit, confirmation_time, is_final, notes |
| **MaterialConsumption** | id, batch_id, material_id, quantity, unit, consumption_time |

### QM

| Entity | Fields |
|--------|--------|
| **QualityInspection** | id, batch_id (unique), inspection_lot (unique), inspection_status, pH, alcohol_percent, temperature, co2_level, appearance, microbiological_status, inspector_notes, inspection_date, result_date |
| **NonConformity** | id, inspection_id, defect_type, defect_code, description, severity, disposition, created_at |

### CO

| Entity | Fields |
|--------|--------|
| **CostRecord** | id, production_order_id (unique), planned_material/labor/machine/energy/total cost, actual_material/labor/machine/energy/total cost |

## Relationships

```
Material 1─N ProductionRecipe ─┬─ N RecipeComponent (→ Material)
                               └─ N RecipeOperation

Material 1─N ProductionOrder (→ Recipe)
ProductionOrder 1─N Batch (→ Resource)
Batch 1─1 QualityInspection ─ N NonConformity
Batch 1─N ProductionConfirmation
Batch 1─N MaterialConsumption (→ Material)
ProductionOrder 1─1 CostRecord
```

## Key constraints

- **Enum CHECK constraints** derived from the Pydantic enums (statuses, types,
  severity, disposition, role).
- **CostRecord** CHECK constraints: `planned_total_cost = Σ planned components`
  and `actual_total_cost = Σ actual components` (tolerance `< 0.01`).
- **ProductionOrder** CHECK: `planned_end > planned_start`, `planned_quantity > 0`.
- **QualityInspection.batch_id** unique (one inspection per batch).

## Enums

- `MaterialType`: FINISHED_PRODUCT, RAW_MATERIAL, SEMI_FINISHED, PACKAGING, AUXILIARY
- `ProductionOrderStatus`: CREATED, RELEASED, IN_PROCESS, COMPLETED, CLOSED, DELIVERED, PARTIAL
- `BatchStatus`: CREATED, IN_PRODUCTION, COMPLETED, REWORK, SCRAP, RELEASED
- `InspectionStatus`: PENDING, IN_PROGRESS, PASSED, FAILED, REWORK, SCRAP
- `DefectSeverity`: CRITICAL, MAJOR, MINOR
- `DefectDisposition`: USE_AS_IS, REWORK, SCRAP, RETURN
- `UserRole`: admin, operator, viewer
