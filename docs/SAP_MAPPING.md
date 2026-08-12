# SAP Mapping

Conceptual mapping to SAP S/4HANA. This project is **inspired by** SAP concepts;
it is **not** an SAP implementation.

| This project | SAP S/4HANA concept |
|--------------|---------------------|
| Material | Material Master (MM) |
| ProductionRecipe (BOM + routing) | Bill of Material (CS01/CS02) + Routing (CA01/CA02) |
| ProductionOrder | Production Order (CO01/CO02) |
| Batch | Batch (MSC1N) |
| ProductionConfirmation | Production Confirmation (CO11N) |
| MaterialConsumption | Goods Issue (MIGO) |
| ProductionResource | Work Center / Resource (CR01) |
| QualityInspection | Inspection Lot (QA01/QA02) |
| NonConformity | Quality Notification (QM01) |
| CostRecord | Cost Object Controlling (CO) / Settlement |
| Status state machines | Status Management (BS22) |
| RBAC (viewer/operator/admin) | Authorization roles (PFCG) |
| PP-PI / QM / CO modules | PP-PI / QM / CO modules |

## Cross-module integration

| This project | SAP concept |
|--------------|-------------|
| `batch.created` → auto inspection | Inspection lot auto-generation on goods receipt (QM) |
| `order.completed` → auto cost record | Cost calculation on order settlement (CO) |
| `inspection.failed` → rework cost | Quality cost / variance posted on usage decision |

## Disclaimer

No SAP proprietary data, code or transactions are reproduced. Mapping is
conceptual, for educational and portfolio purposes.
