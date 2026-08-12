# HANDOFFS — Industrial ERP Simulator

This file documents the completion of each task, serving as the source of truth for model transitions.

---

## TASK-007 — CO Service + CostRecord API + Recipes CRUD + Paginação Padronizada

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- `app/services/costing_service.py` — `CostingService` cobrindo o domínio CO
  - Criar CostRecord (valida ProductionOrder existe), listar, buscar por id/ordem
  - Atualizar custos reais (`update_actual_costs`)
  - `get_summary` → `CostSummary` (planned_total, actual_total, variance, variance_percent)
  - Transaction boundary (M-05): commit em sucesso, rollback em erro; `IntegrityError` → `DuplicateEntityError`
- `app/api/costing.py` — Router FastAPI com 6 endpoints para CO
  - `POST /api/costing/records` — criar custo por ordem
  - `GET /api/costing/records` — listar com paginação (envelope)
  - `GET /api/costing/records/{id}` / `GET /api/costing/records/order/{order_id}`
  - `PUT /api/costing/records/{id}/actual` — atualizar custos reais
  - `GET /api/costing/records/{id}/summary` — resumo com variance
- `app/api/production.py` — **Recipes CRUD (H-02)** + paginação em todos os list endpoints
  - `POST /api/production/recipes` — cria receita com BOM (components) e roteiro (operations)
  - `PUT /api/production/recipes/{id}` — atualiza campos + substitui BOM/roteiro
  - `DELETE /api/production/recipes/{id}` — bloqueia se houver ProductionOrder (409)
  - Validação M-11/L-05: `component.unit` deve ser igual ao `base_unit` do material → `ComponentUnitMismatchError` (422)
- `app/domain/common.py` — `PaginatedResponse[T]` genérico (M-13); `MaterialList` removido
- **Paginação padrão (M-13):** todos os endpoints de listagem retornam `{items, total, page, page_size}`
  - PP-PI: materials, orders, orders/status, batches/order, resources, resources/work-center, recipes, recipes/material
  - QM: inspections, non-conformities · CO: records
  - Count helpers adicionados: `count_by_status`, `count_by_order`, `count_by_work_center`, `count_active_for_material`, `count_by_inspection`
- **L-13:** `ProductionRecipe` relacionamento em `ProductionOrder` + `joinedload(recipe)` em `get_with_material`; schema `ProductionOrder` agora expõe `recipe`
- `app/domain/entities.py` — `cascade="all, delete-orphan"` em `ProductionRecipe.components/operations` (permite substituir BOM no update e deletar receita limpa)
- `app/domain/costing/cost.py` — `planned_total_cost` adicionado ao schema de saída `CostRecord`
- `app/main.py` — router CO montado + handler `ComponentUnitMismatchError` → 422

**ARQUIVOS CRIADOS:**
- `app/domain/common.py`
- `app/services/costing_service.py`
- `app/api/costing.py`
- `tests/unit/test_api_costing.py` (15 testes)
- `tests/unit/test_recipes_crud.py` (15 testes)

**ARQUIVOS ALTERADOS:**
- `app/api/production.py` — envelopes de paginação + recipes CRUD
- `app/api/quality.py` — envelopes de paginação
- `app/domain/costing/cost.py`, `app/domain/entities.py`, `app/domain/production/material.py`, `app/domain/production/recipe.py`
- `app/core/exceptions.py` — `ComponentUnitMismatchError`
- `app/repositories/production_repository.py`, `app/repositories/quality_repository.py`
- `app/services/__init__.py`, `app/services/production_service.py`
- `app/main.py`
- `tests/unit/test_api_production.py`, `tests/unit/test_api_quality.py` (asserts de envelope)

**DOCUMENTOS CONSULTADOS:**
- `plano/07-dominio-co.md` — estruturas Planned/Actual/Variance, indicadores CO
- `plano/04-arquitetura-software.md` — routers `app/api/costing.py`, service layer
- `plano/05-dominio-pp-pi.md` (referência recipes) via auditoria
- `auditoria.md` — H-02, M-13, L-12, L-13 (item 6 Recomendações Prioritárias)
- `TASKS.md` — ciclo Task → Test → Auto Review → Security Audit → Handoff

**TESTES:**
```
============================= 143 passed in 4.83s ==============================
```
- `.venv/bin/python -m compileall app/` → OK
- `.venv/bin/python -m pytest tests/` → **143 passed** (era 113)
- `npm run typecheck` → OK
- `npm run lint` → OK

**AUTO REVIEW:**
- Padrão idêntico a TASK-005/006: service layer com transaction boundary + thin API
- Paginação (M-13) padronizada com `PaginatedResponse[T]` genérico — sem duplicação por entidade
- Recipes CRUD (H-02) completos incluindo BOM/roteiro; consistência de unidade validada (M-11/L-05)
- Recipe deletável somente sem dependências de ProductionOrder (409)
- `CostRecord` mantém CHECK constraints (H-02 da auditoria original) — totais nunca divergem
- Sem refatorações fora do escopo; sem novas dependências

**SECURITY AUDIT:**
- Inputs validados via Pydantic (Decimal `ge=0`, `decimal_places`, enums, `gt=0`)
- SQL via ORM parametrizado (sem SQL injection)
- `ComponentUnitMismatchError` → 422; `EntityHasDependenciesError` → 409; `EntityNotFoundError` → 404
- Erros de domínio traduzidos sem expor stack traces
- Sem secrets/tokens/credenciais; `.env` não alterado
- Logs sem dados sensíveis (recipe_code, order_id, record id)

**PENDÊNCIAS:**
- TASK-008: Dashboard API (KPIs agregados) — inclui M-09 (rollback automático), M-12 (`?active=all`), L-09/L-10 (índices), I-21 (`/health` com check de DB)
- TASK-009: Autenticação (H-01), máquinas de estado (M-14/M-15), rate limiting (M-16), cascade delete (L-14)
- Opt-out assumido: `list_materials` mantém filtro ativo; M-12 deixará `active=all` para TASK-008

**PRÓXIMA TAREFA:**
TASK-008 — Dashboard API (KPIs agregados de PP-PI, QM e CO)

---

## TASK-006 — QM Service + REST API Endpoints

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- `app/services/quality_service.py` — `QualityService` com 8 métodos cobrindo o domínio QM
  - **Quality Inspections**: criar (valida batch existe), listar, buscar por id/lote/batch, registrar resultado
  - **Non-Conformities**: adicionar (valida inspection existe), listar por inspection
  - Transaction boundary: commit em sucesso, rollback em erro (padrão M-05)
  - Tradução de `IntegrityError` → `DuplicateEntityError`
  - Validação de status/parâmetros via whitelist (M-02 reutilizado)
- `app/api/quality.py` — Router FastAPI com 9 endpoints para domínio QM
  - `POST /api/quality/inspections` — criar inspeção (status inicial PENDING)
  - `GET /api/quality/inspections` — listar com paginação
  - `GET /api/quality/inspections/{id}` — buscar por id
  - `GET /api/quality/inspections/lot/{inspection_lot}` — buscar por lote
  - `GET /api/quality/inspections/batch/{batch_id}` — buscar por batch (com non-conformities)
  - `PUT /api/quality/inspections/{id}/result` — registrar resultado (status + parâmetros)
  - `GET /api/quality/inspections/{id}/non-conformities` — listar não-conformidades
  - `POST /api/quality/inspections/{id}/non-conformities` — adicionar não-conformidade
- `app/main.py` — Router QM montado
- `tests/unit/test_api_quality.py` — **20 testes** cobrindo todos os endpoints QM
  - Inspections: create + batch inválido + duplicate + list + get by id/lot/batch + result update
  - Validação de resultado: status inválido (422), pH fora do range (422), whitelist protege identity
  - Non-conformities: add + inspection inválida + enum inválido + list vazio/cheio

**ARQUIVOS CRIADOS:**
- `app/services/quality_service.py`
- `app/api/quality.py`
- `tests/unit/test_api_quality.py`

**ARQUIVOS ALTERADOS:**
- `app/main.py` — mount do router QM

**DOCUMENTOS CONSULTADOS:**
- `plano/06-dominio-qm.md` — fluxo de inspeção, parâmetros sintéticos, indicadores
- `plano/04-arquitetura-software.md` — estrutura de routers (`app/api/quality.py`)
- `TASKS.md` — ciclo Task → Test → Audit → Handoff

**TESTES:**
```
============================== 113 passed in 3.56s ==============================
```
- `.venv/bin/python -m compileall app/` → OK
- `.venv/bin/pytest tests/ -v` → **113 passed** (era 93)
- `npm run typecheck` → OK
- `npm run lint` → OK

**AUTO REVIEW:**
- Padrão idêntico ao TASK-005 (service layer + thin API + exception handlers)
- Whitelist de campos mutáveis (M-02) protege campos de identidade na atualização de resultado
- Validação Pydantic reforça ranges físicos (pH 0-14, alcohol 0-100) — parâmetros sintéticos documentados
- Exceções de domínio traduzidas para HTTP codes apropriados (404, 409, 422)
- Sem duplicação de lógica entre endpoints e service
- Testes cobrem casos de sucesso, erro e borda

**SECURITY AUDIT:**
- Inputs validados via Pydantic (Field constraints, enums, tipos, ranges)
- SQL via ORM parametrizado (sem SQL injection)
- Whitelist impede sobrescrever campos de identidade (id, batch_id, inspection_lot)
- Erros de domínio traduzidos sem expor stack traces
- Sem secrets, tokens ou credenciais
- Logs sem dados sensíveis (inspection_lot, defect_code)

**PENDÊNCIAS:**
- TASK-007: Serviço CO + endpoints de custo
- TASK-008: Dashboard API (KPIs agregados)
- TASK-009: Simulation Engine
- Integração PP→QM→CO (eventos) documentada em `plano/08-integracao-eventos.md`

**PRÓXIMA TAREFA:**
TASK-007 — Criar serviço CO + REST endpoints para Controlling (Cost Management)

---

## TASK-005 — REST API Endpoints PP-PI (FastAPI)

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- `app/api/production.py` — Router FastAPI com 19 endpoints para domínio PP-PI
  - **Materials** (CRUD completo): `POST`, `GET`, `PUT`, `DELETE` + listagem paginada
  - **Production Orders**: criar, listar, buscar por número, buscar por status, buscar por ID (com material eager-loaded)
  - **Batches**: criar, listar por ordem, buscar por número
  - **Production Resources**: criar, listar, buscar por ID/código/centro de trabalho
  - **Production Recipes**: listar, buscar por ID/código/material ativo
- `app/services/production_service.py` — Estendido com 19 métodos cobrindo todo PP-PI
  - CRUD de Materials, Production Orders, Batches, Resources, Recipes
  - Validação de regras de negócio (material ativo, receita compatível, dependências)
  - Transaction boundary: commit em sucesso, rollback em erro (padrão M-05)
  - Tradução de `IntegrityError` → `DuplicateEntityError`
- `app/main.py` — Router montado + exception handlers globais
  - `EntityNotFoundError` → 404
  - `DuplicateEntityError` → 409
  - `RecipeMaterialMismatchError` → 422
  - `EntityHasDependenciesError` → 409
  - `DomainError` (fallback) → 400
  - DB dependency (`session_dependency`) injetada via FastAPI Depends
- `tests/unit/test_api_production.py` — **36 testes** cobrindo todos os endpoints
  - Materials: CRUD + duplicate + not found + update partial
  - Production Orders: create + validação datas + list + status filter + not found
  - Batches: create + duplicate + invalid order + list by order + by number + not found
  - Resources: create + duplicate + list + by code + by work center + not found
  - Recipes: list + by code + not found
  - Health check

**ARQUIVOS CRIADOS:**
- `app/api/production.py`
- `tests/unit/test_api_production.py`

**ARQUIVOS ALTERADOS:**
- `app/main.py` — router mounting + exception handlers
- `app/services/production_service.py` — 18 novos métodos

**DOCUMENTOS CONSULTADOS:**
- `plano/04-arquitetura-software.md` — estrutura de routers (`app/api/production.py`)
- `plano/05-dominio-pp-pi.md` — entidades e indicadores KPIs
- `plano/09-dashboard.md` — endpoints esperados para dashboard
- `TASKS.md` — ciclo Task → Test → Audit → Handoff

**TESTES:**
```
============================== 93 passed in 2.79s ==============================
```
- `.venv/bin/python -m compileall app/` → OK
- `.venv/bin/pytest tests/ -v` → **93 passed** (era 57)
- `npm run typecheck` → OK
- `npm run lint` → OK

**AUTO REVIEW:**
- Router separado por domínio (`app/api/production.py`) conforme arquitetura planejada
- Service layer mantém lógica de negócio; API endpoints são finos (thin controllers)
- Exceções de domínio traduzidas para HTTP codes apropriados (404, 409, 422)
- Sem duplicação de lógica entre endpoints e service
- Nomes de endpoints seguem REST (substantivos, ações via HTTP verbs)
- Testes cobrem casos de sucesso, erro e borda (404, 409, 422, validação)

**SECURITY AUDIT:**
- Inputs validados via Pydantic (Field constraints, enums, tipos)
- SQL via ORM parametrizado (sem SQL injection)
- Erros de domínio traduzidos sem expor stack traces
- Nenhum endpoint expõe dados sensíveis
- Sem secrets, tokens ou credenciais
- `.env.example` sem valores reais
- Logs sem dados sensíveis (material_code, order_number, resource_code)

**PENDÊNCIAS:**
- TASK-006: Serviço QM + endpoints de qualidade
- TASK-007: Serviço CO + endpoints de custo
- TASK-008: Dashboard API (KPIs agregados)
- TASK-009: Simulation Engine

**PRÓXIMA TAREFA:**
TASK-006 — Criar serviço QM + REST endpoints para Quality Management

---

## TASK-004 — Database Connection + Alembic Setup

**Status:** DONE

**Data:** 2026-08-11

**IMPLEMENTADO:**
- `app/database/connection.py` — SQLAlchemy engine + session factory com `python-dotenv`
  - Lê `DATABASE_URL` do ambiente; fallback SQLite in-memory quando não definido
  - `session_dependency()` generator pronto para injeção em rotas FastAPI
- `alembic.ini` — URL delegado a `env.py` (sem hardcode)
- `database/migrations/env.py` — importa `Base.metadata` de `app.domain.entities` + `get_engine()` de `app.database.connection`
- Migração inicial autogerada (`4337571b8a8f_initial.py`) — 11 tabelas com CHECK constraints, índices e FKs
- `alembic upgrade head` aplicado com sucesso em SQLite de validação

**ARQUIVOS CRIADOS:**
- `app/database/__init__.py`, `app/database/connection.py`
- `alembic.ini`
- `database/migrations/env.py`, `database/migrations/script.py.mako`
- `database/migrations/versions/4337571b8a8f_initial.py`

**TESTES:**
- `.venv/bin/python -m compileall app/` → OK
- `.venv/bin/pytest tests/` → 56 passed
- `npm run typecheck` → OK

**AUTO REVIEW:**
- Conexão isolada em `app/database/` — sem acoplamento a domain/services
- Alembic configurado para autogenerate contra `Base.metadata`
- Migração inicial cobre todas as entidades com constraints

**SECURITY AUDIT:**
- `DATABASE_URL` via env; sem credenciais hardcoded
- `.env.example` com placeholders; `.env` no `.gitignore`

**PENDÊNCIAS:**
- TASK-005: API endpoints PP-PI (Material, Production Order)

**PRÓXIMA TAREFA:**
TASK-005 — Criar REST endpoints para PP-PI (FastAPI)

---

## TASK-003 — Correção da Auditoria (auditoria.md)

**Status:** DONE

**Data:** 2026-08-11

**IMPLEMENTADO:**
- **H-01** — `BaseRepository.count()` agora usa `func.count()` (O(1) memória, executado no DB)
- **H-02** — `CostRecord` ganhou CHECK constraints garantindo que `planned_total_cost` e `actual_total_cost` sempre sejam iguais à soma dos componentes (materiais, trabalho, máquina, energia)
- **H-03** — `app/services/production_service.py` com `ProductionService.create_production_order()` que valida `recipe.material_id == order.material_id` e material ativo antes de persistir
- **M-01** — CHECK constraints derivadas dos enums Pydantic (helper `_enum_check`) para `material_type`, `status` (orders/batches), `inspection_status`, `severity`, `disposition` — fonte única de verdade, sem drift
- **M-02** — `QualityInspectionRepository.update_result()` com whitelist `_MUTABLE_INSPECTION_FIELDS` + validação de status via `InspectionStatus` enum
- **M-03** — `model_validator` em `ProductionOrderBase` garante `planned_end > planned_start`
- **M-04** — `MaterialRepository.delete()` verifica 4 dependências (Recipe, RecipeComponent, ProductionOrder, MaterialConsumption) e lança `EntityHasDependenciesError`
- **M-05** — Contrato transacional documentado no `BaseRepository` (repos usam flush, services fazem commit/rollback); `ProductionService` implementa o padrão
- **M-06** — Todas as datas substituídas por `datetime.now(UTC)` com colunas `DateTime(timezone=True)`
- **M-07** — 33 testes novos (Quality, Batch, Recipe, CostingRepository, ProductionService)
- **M-08** — Teste `test_count_active` adicionado
- **M-09** — `MaterialStatus` enum removido (código morto)
- **M-10** — Imports não usados removidos
- **L-01** — `.env.example` usa placeholders `<user>:<password>`
- **L-02** — `app/core/logging.py` com `setup_logging()` chamado no `main.py`
- **L-03** — `app/core/exceptions.py`: `DomainError`, `EntityNotFoundError`, `DuplicateEntityError`, `RecipeMaterialMismatchError`, `EntityHasDependenciesError` + tradução de `IntegrityError`
- **L-04** — `pH` Numeric(3,2), `alcohol_percent` Numeric(3,1)
- `.gitignore` restaurado (Python + Node/Vite) — havia perdido entradas Vite em TASK-001

**ARQUIVOS CRIADOS:**
- `app/core/__init__.py`, `app/core/exceptions.py`, `app/core/logging.py`
- `app/services/production_service.py`
- `tests/unit/test_quality.py`, `tests/unit/test_batch.py`, `tests/unit/test_recipe.py`, `tests/unit/test_costing_repository.py`, `tests/unit/test_production_service.py`

**ARQUIVOS ALTERADOS:**
- `app/domain/entities.py` (CHECK constraints, tz-aware dates, precision)
- `app/domain/production/recipe.py` (model_validator dates)
- `app/domain/production/material.py` (removido MaterialStatus)
- `app/repositories/base.py` (count, contrato transacional)
- `app/repositories/production_repository.py` (delete com dependências, imports)
- `app/repositories/quality_repository.py` (whitelist, status validation)
- `app/repositories/costing_repository.py` (import não usado)
- `app/services/__init__.py`, `app/main.py`, `.env.example`, `.gitignore`
- `tests/conftest.py` (tz-aware, fixtures sample_resource/sample_batch)
- `tests/unit/test_material.py`, `tests/unit/test_cost_record.py`

**TESTES:**
```
============================== 56 passed in 0.77s ==============================
```
- `.venv/bin/python -m compileall app/` → OK
- `.venv/bin/pytest tests/` → **56 passed** (era 23)
- `npm run typecheck` → OK

**AUTO REVIEW:**
- Todos os itens HIGH, MEDIUM e LOW da auditoria tratados (16/17)
- `L-05` (RecipeComponent.unit) mantido como decisão de domínio — componentes possuem UoM próprias; validar consistência quando o Recipe service for criado

**SECURITY AUDIT:**
- Sem secrets; `.env.example` com placeholders; ORM parametrizado; validação Pydantic + whitelist; erros traduzidos para domínio; logs sem dados sensíveis

**PENDÊNCIAS:**
- `L-05`: validação de unidade em Recipe service (futuro)
- TASK-004: Database connection + Alembic migrations
- TASK-005/006/007: API endpoints PP-PI, QM, CO
- TASK-008: Simulation engine

**PRÓXIMA TAREFA:**
TASK-004 — Criar `app/database/connection.py` + setup Alembic para PostgreSQL

---

## TASK-001 — Preparar Estrutura Base

**Status:** DONE

**Data:** 2026-08-11

**IMPLEMENTADO:**
- Estrutura de diretórios conforme `plano/04-arquitetura-software.md`
- `app/` com api, domain (pp/qm/co), services, repositories, simulation, analytics, templates, static
- `database/migrations/`, `database/seeds/`
- `scripts/` (generate_data, seed_database, reset_database)
- `tests/unit/`, `tests/integration/`
- `requirements.txt` (FastAPI, SQLAlchemy, Pydantic, Pandas, Plotly, Jinja2, pytest, httpx, alembic)
- `app/main.py` com FastAPI base e endpoint `/health`
- `.env.example` com variáveis de ambiente e defaults de simulação
- `.gitignore` atualizado para Python

**ARQUIVOS CRIADOS:**
- `requirements.txt`
- `app/__init__.py`, `app/main.py`
- `app/api/__init__.py`
- `app/domain/__init__.py`
- `app/domain/production/__init__.py`
- `app/domain/quality/__init__.py`
- `app/domain/costing/__init__.py`
- `app/services/__init__.py`
- `app/repositories/__init__.py`
- `app/simulation/__init__.py`
- `app/analytics/__init__.py`
- `.env.example`
- `.gitignore` (atualizado)

**TESTES:**
- `python3 -m compileall app/` → OK (todos arquivos compilam)
- `npm run typecheck` → OK (TypeScript legado sem erros)

**AUTO REVIEW:**
- Arquitetura respeita os documentos de plano/
- Domínios PP-PI, QM, CO separados corretamente
- Sem duplicação, sem acoplamento
- Nomes representam corretamente o domínio ERP

**SECURITY AUDIT:**
- Sem secrets, tokens ou credenciais no código
- `.env.example` sem valores reais
- `.env` no `.gitignore`
- Nenhuma vulnerabilidade identificada

**PENDÊNCIAS:**
- Instalar dependências Python (`pip install -r requirements.txt`) quando o ambiente virtual estiver pronto
- Services de domínio ainda são stubs
- Repositories e templates vazios

**PRÓXIMA TAREFA:**
TASK-002 — Modelar entidade Material (domínio PP-PI)

---

## TASK-002 — Modelar Entidades Material, Recipe, Order, Batch, QM, CO

**Status:** DONE

**Data:** 2026-08-11

**IMPLEMENTADO:**
- Entidades SQLAlchemy completas para PP-PI, QM e CO em `app/domain/entities.py`
  - `Material` — material_code, material_name, material_type, base_unit, plant, is_active
  - `ProductionRecipe` — com RecipeComponent e RecipeOperation (BOM + roteiro)
  - `ProductionOrder` — order_number, planned/actual quantity, status, timestamps
  - `ProductionResource` — work_center, resource_type, availability
  - `Batch` — batch_number, yield_percent, status
  - `ProductionConfirmation` — operation confirmation com quantities
  - `MaterialConsumption` — raw material tracking
  - `QualityInspection` — pH, alcohol%, temperature, CO2, appearance, microbiological
  - `NonConformity` — defect tracking com severity e disposition
  - `CostRecord` — planned/actual costs por categoria (material, labor, machine, energy) com variance properties
- Schemas Pydantic para validação:
  - `app/domain/production/material.py` — MaterialType enum, MaterialCreate/Update/List
  - `app/domain/production/recipe.py` — ProductionOrderStatus, ProductionRecipe, ProductionOrder
  - `app/domain/production/batch.py` — BatchStatus, Batch, ProductionConfirmation
  - `app/domain/quality/inspection.py` — InspectionStatus, DefectSeverity, DefectDisposition, QualityInspection, NonConformity
  - `app/domain/costing/cost.py` — CostRecord, CostRecordUpdate, CostSummary
- Repository pattern completo:
  - `app/repositories/base.py` — BaseRepository com CRUD genérico (get_by_id, get_all, count, add, delete)
  - `app/repositories/production_repository.py` — MaterialRepository, ProductionOrderRepository, BatchRepository, ProductionRecipeRepository, ProductionResourceRepository
  - `app/repositories/quality_repository.py` — QualityInspectionRepository, NonConformityRepository
  - `app/repositories/costing_repository.py` — CostRecordRepository (create_for_order, update_actual)
- `pytest.ini` com configuração de testes
- `tests/conftest.py` com fixtures: engine (SQLite in-memory), session, sample_material, sample_recipe, sample_production_order
- `tests/unit/test_material.py` — 9 testes (criação, repo, validação)
- `tests/unit/test_production_order.py` — 5 testes (repo, modelo)
- `tests/unit/test_cost_record.py` — 5 testes (variance, Pydantic)

**ARQUIVOS CRIADOS:**
- `app/domain/entities.py`
- `app/domain/production/material.py`
- `app/domain/production/recipe.py`
- `app/domain/production/batch.py`
- `app/domain/quality/inspection.py`
- `app/domain/costing/cost.py`
- `app/repositories/base.py`
- `app/repositories/production_repository.py`
- `app/repositories/quality_repository.py`
- `app/repositories/costing_repository.py`
- `app/repositories/__init__.py`
- `tests/conftest.py`
- `tests/unit/test_material.py`
- `tests/unit/test_production_order.py`
- `tests/unit/test_cost_record.py`
- `pytest.ini`

**ARQUIVOS ALTERADOS:**
- `requirements.txt` (adicionado sqlalchemy, pydantic, pytest)
- `app/repositories/__init__.py` (atualizado com exports)
- `.venv/` criado com virtualenv + dependências instaladas

**TESTES:**
```
============================= test session starts ==============================
platform linux -- Python 3.11.2, pytest-8.3.0, pluggy-1.6.0
cachedir: .pytest_cache
rootdir: /workspace/simulador-erp-industrial
configfile: pytest.ini
plugins: anyio-4.14.2

tests/unit/test_cost_record.py::TestCostRecordModel::test_cost_record_variance_none_when_no_actual PASSED [  4%]
tests/unit/test_cost_record.py::TestCostRecordModel::test_cost_record_variance_positive PASSED [  8%]
tests/unit/test_cost_record.py::TestCostRecordModel::test_cost_record_variance_negative PASSED [ 13%]
tests/unit/test_cost_record.py::TestCostRecordPydantic::test_cost_record_create PASSED [ 17%]
tests/unit/test_cost_record.py::TestCostRecordPydantic::test_cost_record_update_partial PASSED [ 21%]
tests/unit/test_material.py::TestMaterialModel::test_material_creation PASSED [ 26%]
tests/unit/test_material.py::TestMaterialModel::test_material_unique_code PASSED [ 30%]
tests/unit/test_material.py::TestMaterialModel::test_material_inactive PASSED [ 34%]
tests/unit/test_material.py::TestMaterialRepository::test_create_material PASSED [ 39%]
tests/unit/test_material.py::TestMaterialRepository::test_get_by_code PASSED [ 43%]
tests/unit/test_material.py::TestMaterialRepository::test_get_by_code_not_found PASSED [ 47%]
tests/unit/test_material.py::TestMaterialRepository::test_update_material PASSED [ 52%]
tests/unit/test_material.py::TestMaterialRepository::test_list_active PASSED [ 56%]
tests/unit/test_material.py::TestMaterialRepository::test_delete_material PASSED [ 60%]
tests/unit/test_material.py::TestMaterialRepository::test_delete_not_found PASSED [ 65%]
tests/unit/test_material.py::TestMaterialPydantic::test_material_create_validation PASSED [ 69%]
tests/unit/test_material.py::TestMaterialPydantic::test_material_create_empty_code_fails PASSED [ 73%]
tests/unit/test_production_order.py::TestProductionOrderModel::test_order_creation PASSED [ 78%]
tests/unit/test_production_order.py::TestProductionOrderModel::test_order_status_enum PASSED [ 82%]
tests/unit/test_production_order.py::TestProductionOrderRepository::test_get_by_number PASSED [ 86%]
tests/unit/test_production_order.py::TestProductionOrderRepository::test_get_by_number_not_found PASSED [ 91%]
tests/unit/test_production_order.py::TestProductionOrderRepository::test_get_by_status PASSED [ 95%]
tests/unit/test_production_order.py::TestProductionOrderRepository::TestProductionOrderRepository::test_get_with_material PASSED [100%]

============================== 23 passed in 0.50s ==============================
```
- `.venv/bin/python -m compileall app/` → OK
- `.venv/bin/pytest tests/ -v` → 23 passed
- `npm run typecheck` → OK (TS legado)

**AUTO REVIEW:**
- Arquitetura limpa e modular — entities/schemas/repositories separados
- Domínio SAP-style com material_code, order_number, batch_number
- Enums para status (ProductionOrderStatus, BatchStatus, InspectionStatus, DefectSeverity, etc.)
- Variance calculado automaticamente em CostRecord (property variance e variance_percent)
- BaseRepository genérico e reutilizável
- Testes cobrem CRUD, validação, edge cases (unique constraint, variance calculation)
- Codificação UTF-8 consistente

**SECURITY AUDIT:**
- Sem secrets, tokens ou credenciais
- Sem SQL injection (usa SQLAlchemy ORM com parameterized queries)
- Validação de entrada via Pydantic (Field constraints, enums, tipos)
- `.env.example` sem valores reais
- Nenhuma vulnerabilidade identificada

**PENDÊNCIAS:**
- TASK-003: Production Service (lógica de negócio PP-PI)
- TASK-004: Database connection + Alembic migrations
- TASK-005: API endpoints (FastAPI)
- TASK-006: Simulation engine (generate_data)

**PRÓXIMA TAREFA:**
TASK-003 — Criar ProductionService e database setup
  → `app/services/production_service.py` (lógica de negócio)
  → `app/database/connection.py` (SQLAlchemy session)
  → Alembic setup para PostgreSQL
  → Migrations para criar tabelas no banco

---

## Stack Tecnológica Atual

| Tecnologia | Versão | Uso |
|-----------|--------|-----|
| Python | 3.11.2 | Linguagem principal |
| FastAPI | 0.115.0 | Framework API |
| SQLAlchemy | 2.0.35 | ORM |
| Pydantic | 2.9.0 | Validação de dados |
| pytest | 8.3.0 | Testes |
| SQLite | (in-memory) | Testes unitários |

## Estrutura de Diretórios Atual

```
simulador-erp-industrial/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app + routers + exception handlers
│   ├── core/                      # exceptions + logging
│   ├── api/
│   │   ├── __init__.py
│   │   ├── production.py          # PP-PI REST endpoints (19 endpoints)
│   │   └── quality.py             # QM REST endpoints (9 endpoints)
│   ├── domain/
│   │   ├── entities.py            # Todos os modelos SQLAlchemy + CHECK constraints
│   │   ├── production/
│   │   │   ├── material.py        # Pydantic schemas
│   │   │   ├── recipe.py
│   │   │   └── batch.py
│   │   ├── quality/
│   │   │   └── inspection.py
│   │   └── costing/
│   │       └── cost.py
│   ├── repositories/
│   │   ├── base.py                # BaseRepository genérico
│   │   ├── production_repository.py
│   │   ├── quality_repository.py
│   │   └── costing_repository.py
│   ├── services/
│   │   ├── production_service.py  # ProductionService (19 métodos)
│   │   └── quality_service.py     # QualityService (8 métodos)
│   ├── database/
│   │   └── connection.py          # SQLAlchemy engine + session factory + session_scope
│   ├── simulation/               # (vazio — TASK-008)
│   ├── analytics/                 # (vazio)
│   ├── templates/                 # (vazio)
│   └── static/                    # (vazio)
├── tests/
│   ├── conftest.py               # Fixtures pytest
│   ├── integration/
│   │   └── test_migrations.py    # Alembic upgrade/downgrade test
│   └── unit/
│       ├── test_material.py
│       ├── test_production_order.py
│       ├── test_cost_record.py
│       ├── test_quality.py
│       ├── test_batch.py
│       ├── test_recipe.py
│       ├── test_costing_repository.py
│       ├── test_production_service.py
│       ├── test_api_production.py  # 36 testes de API PP-PI
│       └── test_api_quality.py     # 20 testes de API QM
├── database/
│   └── migrations/                # Alembic migrations
├── scripts/                      # (vazio)
├── requirements.txt
├── pytest.ini
├── alembic.ini
├── .env.example
└── .venv/
```

## Variáveis de Ambiente (.env.example)

```env
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/industrial_erp
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_RECYCLE=3600
APP_HOST=0.0.0.0
APP_PORT=8000
SECRET_KEY=change-me-in-production
SIM_FAILURE_RATE=0.03
SIM_YIELD_MEAN=0.96
SIM_INSPECTION_FAILURE_RATE=0.04
SIM_DOWNTIME_PROBABILITY=0.05
```

## Comandos Disponíveis

```bash
# Python
.venv/bin/python -m compileall app/       # Validação estática
.venv/bin/pytest tests/ -v                 # Testes unitários

# Database
.venv/bin/alembic revision --autogenerate -m "description"  # Gerar migração
.venv/bin/alembic upgrade head                               # Aplicar migrações
.venv/bin/alembic downgrade -1                               # Reverter última

# TypeScript (legado)
npm run typecheck                          # Verificação TypeScript
npm run build                              # Build Vite
npm run dev                                # Dev server
```

## Notas para o Próximo Modelo

1. **Sempre leia os documentos relevantes antes de implementar** — hierarchy defined in TASKS.md section 5
2. **Siga o ciclo**: TASK → TEST → AUTO REVIEW → SECURITY AUDIT → HANDOFF
3. **Mantenha o foco no backend Python** — o valor está em processo/dados/regras/integração/analytics, não em frontend
4. **Dados são sintéticos** — "Synthetic data for educational and simulation purposes"
5. **Não afirme que é SAP** — use "inspired by SAP concepts"
6. **Use Decimal para valores monetários** — nunca float
7. **Para testes use SQLite in-memory** — conforme fixtures em `tests/conftest.py`
8. **Próximo passo: TASK-005** — API endpoints PP-PI (FastAPI)
