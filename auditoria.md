# Relatório de Auditoria — Industrial ERP Simulator

**Revisão de:** TASK-001 e TASK-002
**Data:** 2026-08-11
**Escopo:** Todos os arquivos Python, schemas, repositories, tests, configuração

---

## Sumário

| Severidade | Quantidade |
|-----------|-----------|
| CRITICAL | 0 |
| HIGH | 3 |
| MEDIUM | 10 |
| LOW | 5 |
| INFO | 6 |

---

## HIGH

### H-01 — `BaseRepository.count()` carrega todos os registros na memória

**Arquivo:** `app/repositories/base.py:23-25`
**Problema:** O método `count()` executa `SELECT *` completo e conta em Python com `len(list(...))`. Com crescimento de dados, isso escala linearmente em memória e é uma degradação de performance previsível.

```python
# ATUAL — O(N) em memória
def count(self) -> int:
    stmt = select(self._model)
    return len(list(self._session.execute(stmt).scalars().all()))
```

**Impacto:** Em ~10.000 registros, o consumo de memória e latência já será significativo. Em milhões, pode causar OOM.
**Correção:** Usar `func.count()`:

```python
def count(self) -> int:
    stmt = select(func.count()).select_from(self._model)
    return self._session.scalar(stmt) or 0
```

---

### H-02 — `CostRecord.planned_total_cost` calculado no repo, persistido no DB, sem invariante

**Arquivo:** `app/repositories/costing_repository.py:21-35`, `app/domain/entities.py:193-197`
**Problema:** O `planned_total_cost` é calculado somando os 4 sub-componentes em `create_for_order()` e persistido. Se alguém atualizar os sub-componentes individualmente (ex: `planned_material_cost`) sem recalcular `planned_total_cost`, os dados ficam inconsistentes permanentemente.

**Impacto:** Dashboard CO exibirá variância errada. O princípio "operação → qualidade → dinheiro" perde credibilidade.
**Correção:** Opção A — tornar `planned_total_cost` computed (não persistir). Opção B — adicionar constraint CHECK no DB ou recalcular no `update_actual`.

---

### H-03 — ProductionOrder permite material_id e recipe_id para materiais diferentes

**Arquivo:** `app/domain/entities.py:77-78`, `app/repositories/production_repository.py`
**Problema:** Uma `ProductionOrder` referencia `material_id` (o produto a fabricar) e `recipe_id` (a receita). Não há validação de que o `material_id` do `ProductionOrder` seja o mesmo `material_id` da `ProductionRecipe`. Um erro de integração ou API permitiria criar uma ordem para "Beer 600ml" usando a receita de "Premium Stout".

**Impacto:** Violação conceitual grave do processo ERP. Uma ordem estaria fabricando um material diferente do que a receita descreve.
**Correção:** Validar na service layer que `recipe.material_id == order.material_id` antes de persistir.

---

## MEDIUM

### M-01 — Entidades SQLAlchemy usam String livre para campos que são Enum nos schemas Pydantic

**Arquivos:** `app/domain/entities.py` (várias linhas)
**Problema:** Campos como `material_type` (String(50)), `status` (String(20)), `inspection_status` (String(20)), `severity` (String(10)), `disposition` (String(20)) aceitam qualquer string no banco. Os schemas Pydantic restringem com enums, mas inserções diretas no DB ou via ORM bypassam a validação.

**Impacto:** Dados inconsistentes no banco. Uma query por status "INVALID_STATUS" retornaria resultados inesperados.
**Correção:** Considerar usar SQLAlchemy Enum type, ou adicionar validação explícita nos repositories.

---

### M-02 — `QualityInspectionRepository.update_result()` aceita `**params` sem whitelist

**Arquivo:** `app/repositories/quality_repository.py:35-45`
**Problema:** O método `update_result` aceita `**params` arbitrários e aplica com `setattr` sem verificar se a chave corresponde a um atributo válido da inspeção.

```python
def update_result(self, id: int, status: str, **params) -> QualityInspection | None:
    ...
    for key, value in params.items():
        if value is not None and hasattr(inspection, key):
            setattr(inspection, key, value)  # aceita qualquer atributo
```

**Impacto:** Permite sobrescrever `batch_id`, `inspection_lot`, `inspection_date` — campos que não deveriam ser mutáveis.
**Correção:** Aceitar parâmetros explicitamente ou usar whitelist de campos mutáveis.

---

### M-03 — Sem validação `planned_start < planned_end` em ProductionOrder

**Arquivo:** `app/domain/production/recipe.py:59-60`
**Problema:** `ProductionOrderBase` aceita `planned_start` e `planned_end` independentes. Um usuário pode criar uma ordem onde `planned_end < planned_start`.

**Impacto:** Dados temporais ilógicos. KPIs de tempo de produção seriam negativos.
**Correção:** Adicionar `model_validator` no Pydantic para validar a relação.

---

### M-04 — Material sem verificação de dependências antes de delete

**Arquivo:** `app/repositories/base.py:33-38`
**Problema:** `delete()` remove o Material sem verificar se há `ProductionRecipe`, `ProductionOrder`, `Batch`, `QualityInspection` ou `CostRecord` associados. As FK constraints do DB impedirão a deleção, mas a exceção não é tratada e o comportamento é não-determinístico entre engines.

**Impacto:** Erro não tratado no runtime. Exceção bruta para o usuário.
**Correção:** Verificar dependências antes de deletar, ou implementar soft delete.

---

### M-05 — Sem transaction context para operações multi-entidade

**Arquivo:** `app/repositories/base.py`
**Problema:** Repositories usam `flush()` mas nunca `commit()`. Não há definição de quem gerencia a transação. Em operações como "criar ProductionOrder + RecipeComponents + CostRecord", se uma operação falha no meio, as anteriores ficam em estado inconsistente no session.

**Impacto:** Inconsistência transacional. Depende do caller fazer `commit()` ou `rollback()` corretamente.
**Correção:** Definir um `UnitOfWork` pattern ou documentação explícita de como gerenciar transações.

---

### M-06 — `datetime.utcnow()` deprecated

**Arquivo:** `app/domain/entities.py` (linhas 25, 40, 86, 117, 133, 146, 164, 181, 205, 206)
**Problema:** `datetime.utcnow()` é deprecated desde Python 3.12. Não é timezone-aware, o que pode causar problemas em ambientes multi-timezone.

**Impacto:** Deprecation warnings no Python 3.12+. Timestamps sem timezone.
**Correção:** Usar `datetime.now(timezone.utc)` ou `datetime.now(tz=timezone.utc)`.

---

### M-07 — Sem testes de QualityInspection, Batch, Recipe, CostRecordRepository

**Arquivos:** `tests/unit/`
**Problema:** Os módulos de Quality, Batch e Recipe não têm testes. O `CostRecordRepository` também não é testado diretamente (apenas os models Pydantic).

**Impacto:** Cobertura de testes baixa para o domínio. Bugs em criação de inspeções, batches e receitas passarão despercebidos.
**Correção:** Adicionar testes unitários para:
- `QualityInspectionRepository` (create, get_by_batch, get_by_lot, update_result)
- `NonConformityRepository`
- `BatchRepository`
- `ProductionRecipeRepository` (com components e operations)
- `CostRecordRepository` (create_for_order, update_actual)

---

### M-08 — Teste de `count_active` não coberto

**Arquivo:** `app/repositories/production_repository.py:53-55`, `tests/unit/test_material.py`
**Problema:** `MaterialRepository.count_active()` existe mas não tem teste.

---

### M-09 — `MaterialStatus` enum definido mas nunca usado

**Arquivo:** `app/domain/production/material.py:19-21`
**Problema:** `MaterialStatus` é definido como enum (`ACTIVE`, `INACTIVE`) mas não é referenciado em nenhum schema. `MaterialBase` e `Material` usam `is_active: bool` em vez de `status: MaterialStatus`.

**Impacto:** Código morto. Confusão sobre qual padrão usar.
**Correção:** Remover `MaterialStatus` ou unificar com `is_active`.

---

### M-10 — Import não utilizado em repositories

**Arquivo:** `app/repositories/production_repository.py:3,9`, `app/repositories/quality_repository.py:1`
**Problema:** `ProductionConfirmation` é importada em `production_repository.py` mas nunca usada. `ProductionOrder` é importada em `costing_repository.py` mas nunca usada.

---

## LOW

### L-01 — `.env.example` contém credenciais no formato de string real

**Arquivo:** `.env.example:2`
**Problema:** `DATABASE_URL=postgresql://user:password@localhost:5432/industrial_erp` usa formato real de credencial, mesmo que com valores placeholder. Em um contexto de code review, pode ser confundido com credenciais reais.

**Correção:** Usar formato mais explícito: `DATABASE_URL=postgresql://<user>:<password>@localhost:5432/industrial_erp`

---

### L-02 — Sem logging configurado

**Arquivo:** Todo o projeto
**Problema:** Nenhuma operação de log existe. Para um simulador ERP, é importante registrar: criação de ordens, mudanças de status, falhas de qualidade, cálculos de custo.

**Correção:** Adicionar `logging` com handler adequado antes da fase de API.

---

### L-03 — Sem exception handling customizada

**Arquivo:** Todos os repositories
**Problema:** Exceções de DB (IntegrityError, OperationalError) sobem diretamente sem tradução para mensagens de domínio.

---

### L-04 — Escala DB excessiva para campos de qualidade

**Arquivo:** `app/domain/entities.py:157-160`
**Problema:** `pH` é `Numeric(5,2)` (max 999.99) mas pH vai de 0-14. `alcohol_percent` é `Numeric(4,1)` (max 999.9) mas vai de 0-100.

**Correção:** `pH: Numeric(3,2)`, `alcohol_percent: Numeric(3,1)`. Não crítico mas mais preciso.

---

### L-05 — `RecipeComponent.unit` potencialmente redundante

**Arquivo:** `app/domain/entities.py:53-54`
**Problema:** `RecipeComponent` tem `unit` que pode divergir do `base_unit` do `Material` referenciado. Isso permite inconsistência (componente em KG mas material base em L).

---

## INFO

### I-01 — Autenticação não implementada

**Contexto:** Esperado nesta fase (TASK-001/002). Nenhum endpoint expõe dados. Endpoint `/health` é público por design.
**Ação futura:** Antes do deploy (TASK-009+).

---

### I-02 — Autorização não implementada

**Contexto:** Sem autenticação, autorização é N/A.
**Ação futura:** Após autenticação.

---

### I-03 — CORS não configurado

**Contexto:** FastAPI default não permite CORS. Sem endpoints de dados, é irrelevante agora.
**Ação futura:** Configurar CORS adequado quando o dashboard HTML consumir a API.

---

### I-04 — SSRF não aplicável

**Contexto:** Nenhuma chamada HTTP outbound no código atual.

---

### I-05 — Path traversal não aplicável

**Contexto:** Nenhuma operação de filesystem no código atual.

---

### I-06 — Integração PP→QM→CO pendente

**Contexto:** Documentada em `plano/08-integracao-eventos.md` como tarefa futura. O modelo de eventos ainda não foi implementado. Nenhuma inconsistência existe porque os módulos ainda estão isolados.

---

## Resumo para Correção

| Item | Severidade | Ação Sugerida |
|------|-----------|---------------|
| H-01 `count()` em memória | HIGH | Corrigir em TASK-003 |
| H-02 `planned_total_cost` inconsistente | HIGH | Decidir: computed ou validated |
| H-03 material/recipe mismatch | HIGH | Validar na service layer |
| M-01 String vs Enum | MEDIUM | Padronizar em TASK-003 |
| M-02 `update_result` sem whitelist | MEDIUM | Corrigir em TASK-003 |
| M-03 start/end sem validação | MEDIUM | Adicionar validator |
| M-04 Delete sem dependências | MEDIUM | Verificar antes de deletar |
| M-05 Sem transaction context | MEDIUM | Definir UnitOfWork |
| M-06 `utcnow()` deprecated | MEDIUM | Substituir por `now(tz=...)` |
| M-07 Testes ausentes | MEDIUM | Adicionar em TASK-003 |
| M-08 Teste `count_active` | MEDIUM | Adicionar teste |
| M-09 `MaterialStatus` morto | MEDIUM | Remover |
| M-10 Imports não usados | MEDIUM | Remover |
| L-01 `.env.example` credenciais | LOW | Usar placeholders com `<>` |
| L-02 Sem logging | LOW | Adicionar antes da API |
| L-03 Sem exception handling | LOW | Adicionar handler |
| L-04 Escala DB qualidade | LOW | Ajustar Numeric precision |
| L-05 `RecipeComponent.unit` | LOW | Validar consistência |

Nenhum item CRITICAL encontrado. Os 3 HIGH são corrigíveis sem retrabalho significativo.

---

## Correções Pós-Auditoria (TASK-003)

**Data:** 2026-08-11
**Status:** Corrigido — 16/17 itens tratados
**Validação:** `.venv/bin/pytest tests/` → **56 passed** (era 23); `compileall` OK; `npm run typecheck` OK

| Item | Severidade | Status | Correção Aplicada |
|------|-----------|--------|-------------------|
| H-01 `count()` em memória | HIGH | ✅ Corrigido | `func.count()` executado no DB em `base.py` |
| H-02 totals CO inconsistente | HIGH | ✅ Corrigido | CHECK constraints em `CostRecord` garantem `planned_total_cost`/`actual_total_cost` = soma dos componentes |
| H-03 material/recipe mismatch | HIGH | ✅ Corrigido | `ProductionService.create_production_order()` valida `recipe.material_id == order.material_id` e material ativo |
| M-01 String vs Enum | MEDIUM | ✅ Corrigido | CHECK constraints geradas dos enums Pydantic (helper `_enum_check`) — fonte única de verdade |
| M-02 `update_result` sem whitelist | MEDIUM | ✅ Corrigido | whitelist `_MUTABLE_INSPECTION_FIELDS` + validação de status via `InspectionStatus` |
| M-03 start/end sem validação | MEDIUM | ✅ Corrigido | `model_validator` em `ProductionOrderBase` (planned_end > planned_start) |
| M-04 Delete sem dependências | MEDIUM | ✅ Corrigido | `MaterialRepository.delete()` verifica 4 dependências e lança `EntityHasDependenciesError` |
| M-05 Sem transaction context | MEDIUM | ✅ Corrigido | Contrato documentado no `BaseRepository` (repos flush, services commit/rollback); `ProductionService` implementa |
| M-06 `utcnow()` deprecated | MEDIUM | ✅ Corrigido | `datetime.now(UTC)` + colunas `DateTime(timezone=True)` |
| M-07 Testes ausentes | MEDIUM | ✅ Corrigido | 33 testes novos (Quality, Batch, Recipe, CostingRepo, Service) |
| M-08 Teste `count_active` | MEDIUM | ✅ Corrigido | Teste adicionado em `test_material.py` |
| M-09 `MaterialStatus` morto | MEDIUM | ✅ Corrigido | Enum removido |
| M-10 Imports não usados | MEDIUM | ✅ Corrigido | Removidos |
| L-01 `.env.example` credenciais | LOW | ✅ Corrigido | Placeholders `<user>:<password>` |
| L-02 Sem logging | LOW | ✅ Corrigido | `app/core/logging.py` + `setup_logging()` no `main.py` |
| L-03 Sem exception handling | LOW | ✅ Corrigido | `app/core/exceptions.py` (DomainError e subclasses) + tradução de `IntegrityError` |
| L-04 Escala DB qualidade | LOW | ✅ Corrigido | `pH` Numeric(3,2), `alcohol_percent` Numeric(3,1) |
| L-05 `RecipeComponent.unit` | LOW | ⏸️ Mantido | Decisão de domínio documentada — componentes têm UoM próprias; validar consistência quando o Recipe service for criado |

### Arquivos Criados
- `app/core/__init__.py`, `app/core/exceptions.py`, `app/core/logging.py`
- `app/services/production_service.py`
- `tests/unit/test_quality.py`, `test_batch.py`, `test_recipe.py`, `test_costing_repository.py`, `test_production_service.py`

### Arquivos Alterados
- `app/domain/entities.py` · `app/domain/production/recipe.py` · `app/domain/production/material.py`
- `app/repositories/base.py` · `production_repository.py` · `quality_repository.py` · `costing_repository.py`
- `app/services/__init__.py` · `app/main.py` · `.env.example` · `.gitignore`
- `tests/conftest.py` · `tests/unit/test_material.py` · `tests/unit/test_cost_record.py`

### Revalidação de Segurança
- Sem secrets; `.env.example` sem credenciais reais; ORM parametrizado; validação em Pydantic + whitelist; erros traduzidos para domínio; logs sem dados sensíveis.

---

## Auditoria TASK-004 — Database Connection + Alembic

**Data:** 2026-08-11
**Revisor:** Auditor de Segurança/Qualidade
**Escopo:** Arquivos de TASK-004 (connection.py, alembic.ini, env.py, migração inicial)

### Sumário

| Severidade | Quantidade |
|-----------|-----------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 4 |
| LOW | 4 |
| INFO | 4 |

---

### MEDIUM

**M-11 — Thread safety: `_engine` e `_SessionLocal` sem sincronização**
**Arquivo:** `app/database/connection.py:22-36`
**Problema:** Os globais `_engine` e `_SessionLocal` são inicializados sem lock. Em um app FastAPI multi-threaded, múltiplas requisições podem chamar `get_engine()` simultaneamente, resultando em race condition onde ambas threads veem `_engine is None` e criam engines duplicados.
**Impacto:** Em cenários de alta concorrência, pode causar engines duplicados e leaks de conexão.
**Correção:** Usar `threading.Lock` ou `functools.lru_cache` para garantir inicialização thread-safe.

---

**M-12 — Colunas `is_active`, `status` e `planned_total_cost` sem `server_default`**
**Arquivo:** `database/migrations/versions/4337571b8a8f_initial.py:30,69,123`
**Problema:** As colunas `is_active` (materials, recipes), `status` (orders, batches) e `planned_total_cost` (cost_records) são `nullable=False` mas não têm `server_default` na migração. O Python aplica defaults via ORM, mas inserts via SQL puro falharão.
**Impacto:** Scripts de manutenção, backups restaurados, ou inserts diretos no banco quebrarão sem valores explícitos.
**Correção:** Adicionar `server_default=text("true")` para booleanos e `server_default=text("'CREATED'")` para status nas entidades, ou aceitar o risco documentado.

---

**M-13 — `env.py` sem `render_as_batch=True` para compatibilidade SQLite**
**Arquivo:** `database/migrations/env.py:42-46`
**Problema:** O `context.configure()` não inclui `render_as_batch=True`. SQLite tem suporte limitado a ALTER TABLE (não permite drop columns, rename, add constraints). Sem batch mode, operações futuras em SQLite falharão.
**Impacto:** Desenvolvimento local com SQLite não conseguirá aplicar migrações que envolvam alterações de schema.
**Correção:** Adicionar `render_as_batch=True` ao `context.configure()` em `run_migrations_online()`.

---

**M-14 — Imports não utilizados em `env.py`**
**Arquivo:** `database/migrations/env.py:11`
**Problema:** `engine_from_config` e `pool` são importados mas nunca usados. Resto do template padrão Alembic.
**Impacto:** Código morto, pode confundir desenvolvedores.
**Correção:** Remover imports não utilizados.

---

### LOW

**L-06 — `get_session()` sem padrão context manager para uso standalone**
**Arquivo:** `app/database/connection.py:39-43`
**Problema:** `get_session()` retorna um `Session` sem garantir cleanup automático. Se o caller esquecer de fechar, há leak de conexão.
**Impacto:** Uso incorreto pode causar conexões abertas indefinidamente.
**Correção:** Adicionar `@contextmanager` wrapper ou documentar claramente a responsabilidade do caller.

---

**L-07 — Sem configuração de connection pool exposta**
**Arquivo:** `app/database/connection.py:28-29`
**Problema:** `create_engine()` usa defaults do SQLAlchemy sem expor `pool_size`, `max_overflow`, `pool_recycle`. Para produção, esses valores devem ser ajustáveis.
**Impacto:** Defaults podem não ser ideais para ambientes de produção com alta concorrência ou conexões instáveis.
**Correção:** Expor parâmetros via `.env` (ex: `DB_POOL_SIZE`, `DB_POOL_RECYCLE`).

---

**L-08 — Sem testes de downgrade Alembic**
**Arquivo:** `database/migrations/`
**Problema:** Não há teste que verifica se `alembic downgrade -1` funciona corretamente.
**Impacto:** Downgrade pode falhar silenciosamente em produção, impedindo rollbacks.
**Correção:** Adicionar teste que aplica e reverte a migração inicial.

---

**L-09 — Duplicação de lógica de URL entre `connection.py` e `env.py`**
**Arquivo:** `app/database/connection.py:20`, `database/migrations/env.py:24-25`
**Problema:** Ambos os arquivos definem a mesma lógica: `os.getenv("DATABASE_URL", "sqlite:///:memory:")`. Se a fallback mudar, precisa atualizar em dois lugares.
**Impacto:** Risco de inconsistência se o fallback for alterado.
**Correção:** Centralizar em uma função `_get_database_url()` em `connection.py` e importar em `env.py`.

---

### INFO

**I-07 — `load_dotenv()` modifica ambiente global no import**
**Arquivo:** `app/database/connection.py:18`
**Comportamento:** `load_dotenv()` sem `override=False` explícito pode sobrescrever variáveis de ambiente já definidas.
**Impacto:** Em testes ou containers, variáveis do host podem ser sobrescritas por `.env`.
**Observação:** Comportamento padrão é seguro (`override=False`), mas seria mais explícito.

---

**I-08 — `session_dependency()` não gerencia transações**
**Arquivo:** `app/database/connection.py:46-52`
**Comportamento:** O generator apenas fornece o session e fecha após uso. Não faz commit/rollback.
**Impacto:** Routes que esquecem de commitar perdem alterações silenciosamente.
**Observação:** Por design, services gerenciam transações. Mas poderia ser mais explícito no docstring.

---

**I-09 — Sem logging em `connection.py`**
**Arquivo:** `app/database/connection.py`
**Observação:** Não há logging de eventos de conexão (engine created, session created, errors).
**Impacto:** Debug de problemas de conexão em produção fica mais difícil.
**Correção:** Adicionar `logger.info("Database engine created")` após `_build_engine()`.

---

**I-10 — Migração não inclui `server_default` para `created_at`**
**Arquivo:** `database/migrations/versions/4337571b8a8f_initial.py:31,53,70,108,129,172,188`
**Observação:** Todas as colunas `created_at` usam Python default (`default=_utcnow`) mas não têm `server_default` (ex: `server_default=func.now()`).
**Impacto:** Inserts via SQL puro falharão ou resultarão em NULL para `created_at`.
**Correção:** Adicionar `server_default=func.now()` nas entidades para todas as colunas de timestamp.

---

### Resumo para Correção TASK-004

| Item | Severidade | Ação Sugerida |
|------|-----------|---------------|
| M-11 Thread safety | MEDIUM | Adicionar lock ou lru_cache |
| M-12 Colunas sem server_default | MEDIUM | Adicionar server_default ou documentar risco |
| M-13 render_as_batch para SQLite | MEDIUM | Adicionar render_as_batch=True |
| M-14 Imports não usados env.py | MEDIUM | Remover imports mortos |
| L-06 get_session sem context manager | LOW | Adicionar wrapper ou documentação |
| L-07 Sem config de pool | LOW | Expor via .env |
| L-08 Sem teste de downgrade | LOW | Adicionar teste |
| L-09 Duplicação URL logic | LOW | Centralizar em função |
| I-07 load_dotenv override | INFO | Explicitar override=False |
| I-08 session_dependency transações | INFO | Documentar responsabilidade |
| I-09 Sem logging connection | INFO | Adicionar logs |
| I-10 created_at sem server_default | INFO | Adicionar server_default |
- Sem secrets; `.env.example` sem credenciais reais; ORM parametrizado; validação em Pydantic + whitelist; erros traduzidos para domínio; logs sem dados sensíveis.

---

## Correções Pós-Auditoria TASK-004

**Data:** 2026-08-12
**Status:** Corrigido — 12/12 itens tratados
**Validação:** `PYTHONPATH=. pytest tests/` → **57 passed** (era 56); `compileall` OK; `npm run typecheck` OK; `npm run lint` OK

| Item | Severidade | Status | Correção Aplicada |
|------|-----------|--------|-------------------|
| M-11 Thread safety | MEDIUM | ✅ Corrigido | `threading.Lock` com double-check locking em `get_engine()` e `get_session()` |
| M-12 Colunas sem server_default | MEDIUM | ✅ Corrigido | `server_default` adicionado para `is_active`, `status`, `planned_total_cost` em entidades e migration |
| M-13 render_as_batch para SQLite | MEDIUM | ✅ Corrigido | `render_as_batch=True` adicionado em `run_migrations_offline()` e `run_migrations_online()` |
| M-14 Imports não usados env.py | MEDIUM | ✅ Corrigido | Removidos `engine_from_config` e `pool` |
| L-06 get_session sem context manager | LOW | ✅ Corrigido | Adicionado `session_scope()` context manager em `connection.py` |
| L-07 Sem config de pool | LOW | ✅ Corrigido | `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE` expostos via `.env` |
| L-08 Sem teste de downgrade | LOW | ✅ Corrigido | Teste adicionado em `tests/integration/test_migrations.py` |
| L-09 Duplicação URL logic | LOW | ✅ Corrigido | Função `get_database_url()` centralizada em `connection.py` e reutilizada em `env.py` |
| I-07 load_dotenv override | INFO | ✅ Corrigido | `override=False` explicitado no `load_dotenv()` |
| I-08 session_dependency transações | INFO | ✅ Corrigido | Docstring documenta que services são responsáveis por commit/rollback |
| I-09 Sem logging connection | INFO | ✅ Corrigido | `logger.info("Database engine created")` após inicialização |
| I-10 created_at sem server_default | INFO | ✅ Corrigido | `server_default=func.now()` adicionado em todas as colunas `created_at` |

### Arquivos Criados
- `tests/integration/test_migrations.py`

### Arquivos Alterados
- `app/database/connection.py`
- `app/domain/entities.py`
- `database/migrations/env.py`
- `database/migrations/versions/4337571b8a8f_initial.py`
- `.env.example`

### Revalidação de Segurança
- Thread safety garantida com double-check locking pattern
- Server defaults garantem consistência em inserts via SQL puro
- Logs sem dados sensíveis (URL sem credenciais)
- Pool configuration exposta para tuning em produção

---

## Auditoria TASK-005 — REST API Endpoints PP-PI

**Data:** 2026-08-12
**Revisor:** Auditor de Segurança/Qualidade
**Escopo:** `app/api/production.py`, `app/main.py`, `app/services/production_service.py`

### Sumário

| Severidade | Quantidade |
|-----------|-----------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 0 |
| INFO | 1 |

---

### INFO

**I-11 — Autenticação/Autorização não implementada**
**Arquivo:** `app/api/production.py`
**Observação:** Nenhum endpoint requer autenticação. Esperado nesta fase (TASK-005). Antes do deploy (TASK-009+).
**Ação futura:** Adicionar middleware de autenticação antes de expor endpoints.

---

### Revalidação de Segurança

| Verificação | Resultado |
|------------|-----------|
| Secrets no código | ✅ Nenhum |
| SQL injection | ✅ ORM parametrizado |
| Input validation | ✅ Pydantic (Field, enums, tipos) |
| Stack traces em erros | ✅ Erros de domínio traduzidos (404/409/422) |
| Endpoints sensíveis expostos | ✅ Sem dados sensíveis nos responses |
| CORS excessivo | N/A — sem endpoints de dados ainda |
| Logs com dados sensíveis | ✅ Apenas códigos (material_code, order_number) |

**Resultado:** Nenhum item de segurança encontrado. API pronta para TASK-006 (QM).

---

## Auditoria TASK-006 — QM Service + REST API Endpoints

**Data:** 2026-08-12
**Revisor:** Auditor de Segurança/Qualidade
**Escopo:** `app/api/quality.py`, `app/services/quality_service.py`, `app/main.py`

### Sumário

| Severidade | Quantidade |
|-----------|-----------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 0 |
| INFO | 1 |

---

### INFO

**I-12 — Integração PP→QM (auto-trigger de inspeção) pendente**
**Arquivo:** `app/services/quality_service.py`
**Observação:** O plano `06-dominio-qm.md` define que toda ordem de produção gera automaticamente uma inspeção de qualidade vinculada ao batch. Atualmente a criação é manual via endpoint.
**Ação futura:** Na TASK-008 (Integração/Simulação) ou quando os eventos forem implementados.

---

### Revalidação de Segurança

| Verificação | Resultado |
|------------|-----------|
| Secrets no código | ✅ Nenhum |
| SQL injection | ✅ ORM parametrizado |
| Input validation | ✅ Pydantic (Field, enums, ranges físicos pH 0-14) |
| Stack traces em erros | ✅ Erros de domínio traduzidos (404/409/422) |
| Fields imutáveis | ✅ Whitelist `_MUTABLE_INSPECTION_FIELDS` protege identidade |
| Logs com dados sensíveis | ✅ Apenas códigos (inspection_lot, defect_code) |
| CORS excessivo | N/A — sem endpoints de dados ainda |

**Resultado:** Nenhum item de segurança encontrado. API pronta para TASK-007 (CO).

---

## Auditoria Completa Pós-TASK-006 — Estado Consolidado

**Data:** 2026-08-12  
**Revisor:** Auditor de Segurança/Qualidade  
**Escopo:** Codebase completo após TASK-006 (PP-PI + QM API)  
**Status:** 113 testes passando, typecheck OK, lint OK

### Sumário

| Severidade | Quantidade |
|-----------|-----------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 8 |
| LOW | 10 |
| INFO | 10 |

---

## HIGH

### H-01 — Ausência de Autenticação/Autorização

**Arquivo:** `app/main.py`, todos os routers  
**Problema:** Todos os endpoints REST estão publicamente acessíveis sem autenticação ou autorização. Qualquer usuário pode criar, modificar ou deletar materiais, ordens, batches, inspeções.

**Impacto:** Em produção, permitiria manipulação não autorizada de dados industriais críticos.

**Correção:** 
- Adicionar middleware de autenticação (JWT, OAuth2) em TASK-009
- Implementar roles e permissões (admin, operator, viewer)
- Proteger endpoints sensíveis (DELETE, PUT)

**Prioridade:** Alta (bloqueante para produção)

---

### H-02 — ProductionRecipe sem API CRUD

**Arquivo:** `app/api/production.py`  
**Problema:** Não existem endpoints para criar, listar, atualizar ou deletar `ProductionRecipe`. O domínio PP-PI requer receitas para criar ordens de produção, mas não há forma de criá-las via API.

**Impacto:** Impossível criar receitas via REST API. Apenas via código Python ou SQL direto.

**Correção:**  
Adicionar endpoints em `app/api/production.py`:
- `POST /api/production/recipes`
- `GET /api/production/recipes`
- `GET /api/production/recipes/{id}`
- `PUT /api/production/recipes/{id}`
- `DELETE /api/production/recipes/{id}`

**Prioridade:** Alta (bloqueante para uso da API)

---

## MEDIUM

### M-09 — Session Dependency sem Commit/Rollback

**Arquivo:** `app/database/connection.py:82-92`  
**Problema:** `session_dependency()` cria nova sessão e fecha ao final, mas não gerencia transações. Serviços devem chamar `commit()`/`rollback()` corretamente. Se um serviço falhar em fazer rollback após exceção, a sessão fica em estado inconsistente.

**Impacto:** Possível vazamento de transações não finalizadas, locks de banco.

**Correção:**
```python
def session_dependency():
    session = get_session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

**Prioridade:** Média

---

### M-10 — update_result() sem Validação de Campos

**Arquivo:** `app/repositories/quality_repository.py:58-75`  
**Problema:** `update_result()` aceita `**params` arbitrários. Embora haja whitelist para campos de identidade (`id`, `batch_id`, `inspection_lot`, `inspection_date`), qualquer outro campo pode ser sobrescrito sem validação de tipo ou range.

**Impacto:** Permite definir valores inválidos (ex: `pH="texto"` ou `alcohol_percent=200`) que passarão pelo Pydantic mas podem causar erros no banco.

**Correção:**  
Validar explicitamente cada campo recebido contra os constraints do modelo ou usar `QualityInspectionResult` schema para validar antes de aplicar.

**Prioridade:** Média

---

### M-11 — Inconsistência RecipeComponent.unit vs Material.base_unit

**Arquivo:** `app/domain/entities.py`, `app/domain/production/recipe.py`  
**Problema:** `RecipeComponent.unit` é independente de `Material.base_unit`. Permite inconsistência: componente definido em "KG" mas material base em "L".

**Impacto:** Dados inconsistentes no domínio. Cálculos de custo e consumo podem falhar.

**Correção:**  
- Adicionar validação no service: `if component.unit != material.base_unit: raise ValidationError`
- Ou normalizar automaticamente usando `Material.base_unit`

**Prioridade:** Média (afeta integridade de domínio)

---

### M-12 — list_materials() Retorna Apenas Ativos

**Arquivo:** `app/repositories/production_repository.py:74-76`, `app/api/production.py:21-33`  
**Problema:** `list_active()` filtra `is_active == True`. Não há forma de listar materiais inativos via API (ex: para admin revisar ou reativar).

**Impacto:** Impossível gerenciar ciclo de vida completo de materiais via API.

**Correção:**  
Adicionar query parameter `?active=true|false|all` ou endpoint separado `/api/production/materials/inactive`.

**Prioridade:** Média

---

### M-13 — Paginação Inconsistente

**Arquivo:** `app/api/production.py`  
**Problema:** Apenas `list_materials()` retorna `MaterialList` com metadados de paginação (`total`, `page`, `page_size`). Outros endpoints de listagem (`list_orders`, `list_batches`, `list_inspections`) retornam listas simples sem metadados.

**Impacto:** API inconsistente. Cliente não sabe quantos registros existem ou em qual página está.

**Correção:**  
Padronizar resposta de listagem com envelope:
```python
class PaginatedResponse(BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
```

**Prioridade:** Média

---

### M-14 — ProductionOrder.status sem Validação de Transição

**Arquivo:** `app/domain/production/recipe.py`, `app/services/production_service.py`  
**Problema:** `ProductionOrderBase` aceita qualquer `ProductionOrderStatus` sem validar transições de estado. Permite ir de `CREATED` direto para `COMPLETED` sem passar por `RELEASED` ou `IN_PROCESS`.

**Impacto:** Viola regras de negócio industriais. Ordens podem pular etapas obrigatórias.

**Correção:**  
Implementar máquina de estados no service:
```python
VALID_TRANSITIONS = {
    "CREATED": ["RELEASED"],
    "RELEASED": ["IN_PROCESS"],
    "IN_PROCESS": ["COMPLETED", "PARTIAL"],
    ...
}
```

**Prioridade:** Média (afeta fluxo de produção)

---

### M-15 — QualityInspection sem Validação de Transição de Status

**Arquivo:** `app/services/quality_service.py:77-90`  
**Problema:** `update_inspection_result()` aceita qualquer `InspectionStatus` sem validar transições. Permite ir de `PASSED` para `PENDING` ou de `FAILED` para `PASSED` sem re-inspeção.

**Impacto:** Viola fluxo de qualidade. Inspeções podem ser manipuladas para bypass de controles.

**Correção:**  
Validar transições permitidas:
```python
VALID_TRANSITIONS = {
    "PENDING": ["IN_PROGRESS"],
    "IN_PROGRESS": ["PASSED", "FAILED", "REWORK"],
    "REWORK": ["IN_PROGRESS"],
    ...
}
```

**Prioridade:** Média

---

### M-16 — Ausência de Rate Limiting

**Arquivo:** `app/main.py`  
**Problema:** Nenhum endpoint possui rate limiting. Vulnerável a ataques de negação de serviço (DoS) ou abuso de API.

**Impacto:** Em produção, um cliente malicioso pode sobrecarregar o servidor.

**Correção:**  
Adicionar middleware de rate limiting (ex: `slowapi` ou `fastapi-limiter`).

**Prioridade:** Média (relevante para produção)

---

## LOW

### L-07 — Logging sem Arquivo de Log

**Arquivo:** `app/core/logging.py:16-23`  
**Problema:** `setup_logging()` configura apenas handler para stdout. Não há rotação de logs, arquivo de log, ou configuração de nível por módulo.

**Impacto:** Logs perdidos ao reiniciar container. Difícil debug em produção.

**Correção:**  
Adicionar `RotatingFileHandler` ou configurar via variável de ambiente (`LOG_FILE`, `LOG_LEVEL`).

**Prioridade:** Baixa

---

### L-08 — Ausência de Request ID

**Arquivo:** `app/main.py`, `app/core/logging.py`  
**Problema:** Logs não incluem ID de requisição. Em cenários concorrentes, difícil correlacionar logs de uma mesma requisição.

**Impacto:** Debug difícil em produção com múltiplas requisições simultâneas.

**Correção:**  
Adicionar middleware que gera `X-Request-ID` e injeta no contexto de log.

**Prioridade:** Baixa

---

### L-09 — Índice Ausente em production_orders.status

**Arquivo:** `app/domain/entities.py:115`, `database/migrations/versions/4337571b8a8f_initial.py:69`  
**Problema:** Coluna `status` em `production_orders` não tem índice. Queries como `get_by_status()` farão scan completo da tabela.

**Impacto:** Performance degrada com crescimento de dados.

**Correção:**  
Adicionar `index=True` na definição da coluna.

**Prioridade:** Baixa

---

### L-10 — Índice Ausente em quality_inspections.inspection_status

**Arquivo:** `app/domain/entities.py:201`  
**Problema:** Coluna `inspection_status` não tem índice. Queries filtrando por status serão lentas.

**Impacto:** Performance degrada com crescimento de dados.

**Correção:**  
Adicionar `index=True` na definição da coluna.

**Prioridade:** Baixa

---

### L-11 — CostRecordRepository.update_actual() sem Validação

**Arquivo:** `app/repositories/costing_repository.py:37-51`  
**Problema:** `update_actual()` calcula `actual_total_cost` mesmo se apenas alguns campos `actual_*` foram definidos. Campos não definidos são tratados como `0` via `or Decimal("0")`.

**Impacto:** Totais incorretos se usuário atualizar parcialmente custos reais.

**Correção:**  
Validar que todos os campos `actual_*` estão definidos antes de calcular total, ou documentar comportamento.

**Prioridade:** Baixa

---

### L-12 — Ausência de API para CostRecord (CO)

**Arquivo:** `app/api/`  
**Problema:** Domínio CO (`CostRecord`) não possui endpoints REST. Apenas repository e schemas existem.

**Impacto:** Impossível gerenciar custos via API. Módulo CO inacessível.

**Correção:**  
Implementar `app/api/costing.py` com endpoints CRUD em TASK-007.

**Prioridade:** Baixa (esperado para TASK-007)

---

### L-13 — ProductionOrder.get_with_material() não Carrega Recipe

**Arquivo:** `app/repositories/production_repository.py:91-97`  
**Problema:** `get_with_material()` usa `joinedload` para carregar `Material`, mas não carrega `ProductionRecipe`. Schema `ProductionOrder` espera `recipe` relacionado.

**Impacto:** Dados da receita não disponíveis na resposta da API.

**Correção:**  
Adicionar `.options(joinedload(ProductionOrder.material), joinedload(ProductionOrder.recipe))` ou lazy load.

**Prioridade:** Baixa

---

### L-14 — Ausência de Cascade Delete

**Arquivo:** `app/domain/entities.py`  
**Problema:** Relacionamentos não configuram `cascade="all, delete-orphan"`. Deletar `ProductionOrder` falhará se houver `Batch` relacionado.

**Impacto:** Erro de integridade referencial ao tentar deletar entidades com dependências.

**Correção:**  
- Adicionar cascade para relacionamentos pai-filho
- Ou implementar soft delete
- Ou validar dependências antes de deletar (como `MaterialRepository.delete()` faz)

**Prioridade:** Baixa

---

### L-15 — MaterialUpdate permite Alterar material_code

**Arquivo:** `app/domain/production/material.py:31-34`, `app/repositories/production_repository.py:46-57`  
**Problema:** Schema `MaterialUpdate` não inclui `material_code`, mas repository usa `model_dump(exclude_unset=True)` e aplica qualquer campo recebido. Se `material_code` for passado, será aplicado.

**Impacto:** Inconsistência se código for alterado após criação (código deve ser imutável).

**Correção:**  
- Remover `material_code` do `MaterialBase` e criar `MaterialCreate` separado
- Ou validar explicitamente no repository que `material_code` não pode ser alterado

**Prioridade:** Baixa

---

### L-16 — Testes com IDs Hardcoded

**Arquivo:** `tests/unit/test_api_quality.py`, `tests/unit/test_api_production.py`  
**Problema:** Testes assumem IDs sequenciais (ex: `material_id=1`, `batch_id=1`). Se testes rodarem em ordem diferente ou com dados pré-existentes, falharão.

**Impacto:** Testes frágeis, dependem de estado global.

**Correção:**  
Capturar IDs retornados das responses e usar nos asserts:
```python
response = client.post("/api/production/materials", json=...)
material_id = response.json()["id"]
```

**Prioridade:** Baixa

---

## INFO

### I-13 — CORS não Configurado

**Arquivo:** `app/main.py`  
**Observação:** FastAPI não configura CORS por padrão. Frontend (se houver) não conseguirá consumir API.

**Ação Futura:** Configurar CORS em TASK-009 quando integrar frontend.

---

### I-14 — HTTPS não Forçado

**Observação:** API não força HTTPS. Depende de reverse proxy (nginx, Cloudflare).

**Ação Futura:** Configurar reverse proxy com TLS.

---

### I-15 — Ausência de Timeout de Request

**Observação:** FastAPI usa timeout padrão. Queries longas podem bloquear worker.

**Ação Futura:** Configurar timeout via middleware ou query optimizer.

---

### I-16 — OpenAPI sem Customização

**Arquivo:** `app/main.py:19-23`  
**Observação:** Documentação OpenAPI usa padrões. Não há descrição detalhada, exemplos, ou tags organizadas.

**Ação Futura:** Customizar `app.description`, adicionar `response_model` com exemplos.

---

### I-17 — ProductionResource.is_available sem API de Update

**Arquivo:** `app/domain/entities.py:132-142`  
**Observação:** Campo `is_available` existe mas não há endpoint para alterá-lo.

**Ação Futura:** Adicionar `PUT /api/production/resources/{id}/availability`.

---

### I-18 — Ausência de Soft Delete

**Observação:** Sistema usa hard delete. Dados deletados são perdidos permanentemente.

**Ação Futura:** Considerar soft delete com campo `deleted_at` para auditoria.

---

### I-19 — Ausência de Audit Trail

**Observação:** Mudanças de status (ex: `ProductionOrder.status`) não são registradas com timestamp, usuário, ou motivo.

**Ação Futura:** Criar tabela `status_history` ou usar biblioteca de audit (ex: `sqlalchemy-continuum`).

---

### I-20 — QualityInspection.batch_id unique não Documentado

**Arquivo:** `app/domain/entities.py:199`  
**Observação:** `batch_id` tem `unique=True`, enforce "uma inspeção por batch". Schema Pydantic não documenta essa restrição.

**Ação Futura:** Adicionar `description="One inspection per batch"` no schema.

---

### I-21 — Ausência de Health Check de Banco

**Arquivo:** `app/main.py:56-58`  
**Observação:** Endpoint `/health` retorna `{"status": "ok"}` mas não verifica conectividade com banco.

**Correção:**
```python
@app.get("/health")
def health(session: Session = Depends(session_dependency)):
    try:
        session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail="Database unavailable")
```

**Prioridade:** Baixa

---

### I-22 — Testes Dependem de Ordem de Execução

**Observação:** Testes de API criam dados com IDs esperados. Se pytest rodar em ordem aleatória, podem falhar.

**Correção:**  
Usar fixtures que criam dados isolados ou capturar IDs dinamicamente.

---

## Auditoria TASK-007 — CO Service + Recipes API + Paginação

**Data:** 2026-08-12
**Revisor:** Auditor de Segurança/Qualidade (pós-implementação)
**Escopo:** TASK-007 — `CostingService`, API CO, Recipes CRUD, paginação padronizada (M-13), `get_with_material` com recipe (L-13).

### Sumário

| Severidade | Quantidade |
|-----------|-----------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 2 |
| LOW | 3 |
| INFO | 2 |

---

### Itens Anteriores Resolvidos na TASK-007

| Item | Severidade | Status | Correção Aplicada |
|------|-----------|--------|-------------------|
| H-02 (2ª auditoria) Recipes sem API CRUD | HIGH | ✅ Corrigido | `POST/PUT/DELETE /api/production/recipes` com BOM (components) e roteiro (operations); validação de material ativo e dependências |
| M-11 (2ª auditoria) Unit inconsistency RecipeComponent | MEDIUM | ✅ Corrigido | `ComponentUnitMismatchError` valida `component.unit == material.base_unit` em create e update de recipe |
| M-13 Paginação inconsistente | MEDIUM | ⚠️ Parcialmente | Envelope `PaginatedResponse[T]` genérico criado e aplicado em todos endpoints top-level. **Porém sub-endpoints não paginam de fato** — ver novo **M-17** |
| L-05 `RecipeComponent.unit` | LOW | ✅ Corrigido | Validação de consistência de unidade via `ComponentUnitMismatchError` (422) |
| L-12 Ausência de API para `CostRecord` (CO) | LOW | ✅ Corrigido | `app/api/costing.py` + `app/services/costing_service.py` com 6 endpoints (create, list, get, get_by_order, update_actual, summary) |
| L-13 `get_with_material()` não carregava Recipe | LOW | ✅ Corrigido | Novo relationship `ProductionOrder.recipe`; `joinedload(ProductionOrder.recipe)` em `get_with_material()`; schema `ProductionOrder` expõe `recipe` |
| L-14 Ausência de Cascade Delete | LOW | ⚠️ Parcialmente | `ProductionRecipe.components/operations` agora têm `cascade="all, delete-orphan"`. **`ProductionOrder→Batches` permanece sem cascade** — reservado para TASK-009 |

---

### MEDIUM (novos achados TASK-007)

#### M-17 — Paginação incompleta em sub-endpoints (envelope engana)

**Arquivo:** `app/api/production.py:117-129, 165-177, 208-220`, `app/api/quality.py:73-85`
**Problema:** Endpoints que filtram por pai (`/batches/order/{order_id}`, `/resources/work-center/{work_center}`, `/recipes/material/{material_id}`, `/inspections/{id}/non-conformities`) retornam envelope `PaginatedResponse` com `page`/`page_size`/`total`, **mas não aplicam offset/limit** nos resultados. Os `items` contêm **TODOS** os registros do filtro, não apenas uma página.

**Root cause:** métodos de serviço (`list_batches_by_order`, `list_resources_by_work_center`, `list_active_recipes_for_material`, `list_non_conformities`) não recebem `skip`/`limit`; repositories (`get_by_order`, `get_by_work_center`, `get_active_for_material`, `get_by_inspection`) não aplicam offset/limit.

**Impacto:**
- Envelope sugere paginação, mas entrega tudo. Cliente que confia em `page_size=100` e `total=500` esperará 100 itens, receberá 500.
- Em dados grandes, excede limites de memória do cliente ou da rede.
- Inconsistente com endpoints top-level (`/materials`, `/orders`, `/resources`, `/recipes`) que paginam corretamente.

**Correção sugerida:**
1. Adicionar `skip`/`limit` nos métodos de serviço correspondentes
2. Adicionar offset/limit nos repositories (`get_by_order`, `get_by_work_center`, `get_active_for_material`, `get_by_inspection`)
3. Alternativamente, documentar que sub-endpoints não paginam e **remover metadados enganosos** (usar lista simples ou envelope sem `page`/`page_size`)

**Prioridade:** Média

---

#### M-18 — N+1 queries em `list_orders` e `list_recipes`

**Arquivo:** `app/repositories/base.py:25-27`, `app/repositories/production_repository.py:83-113`
**Problema:** A TASK-007 adicionou `recipe: Optional[ProductionRecipe]` ao schema `ProductionOrder` (L-13). Porém `BaseRepository.get_all()` (usado por `list_orders` e `list_recipes`) não faz `joinedload`. A serialização de cada `ProductionOrder` dispara lazy load de `recipe` (1 query extra × N orders). A serialização de cada `ProductionRecipe` dispara lazy load de `components` e `operations` (2 queries extras × N recipes).

**Impacto:**
- `/orders` com 100 ordens: 1 + 100 = 101 queries
- `/recipes` com 50 receitas: 1 + 50 + 100 = 151 queries
- Performance degrada linearmente em produção

**Correção sugerida:**
- Override em `ProductionOrderRepository.get_all()` com `joinedload(ProductionOrder.material, ProductionOrder.recipe)`
- Override em `ProductionRecipeRepository.get_all()` com `joinedload(ProductionRecipe.components, ProductionRecipe.operations)`
- Ou criar métodos específicos (`list_with_relations`) para endpoints que precisam

**Prioridade:** Média

---

### LOW (novos achados TASK-007)

#### L-17 — `list_orders_by_status` aceita status não-enum

**Arquivo:** `app/api/production.py:95-107`
**Problema:** Query param `status` é `str` genérico. Valor "INVALID" ou qualquer string arbitrária retorna envelope vazio com 200, em vez de validar contra `ProductionOrderStatus` e retornar 422.

**Impacto:** Baixo — retorna resultado correto (vazio), mas falha em sinalizar input inválido ao cliente.

**Correção sugerida:**
```python
def list_orders_by_status(
    status: ProductionOrderStatus,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    ...
):
```

**Prioridade:** Baixa

---

#### L-18 — `update_recipe` sem rollback explícito após modificar relacionamentos

**Arquivo:** `app/services/production_service.py:309-319`
**Problema:** `recipe.components = []` com `cascade="all, delete-orphan"` marca os RecipeComponent antigos para deleção no próximo flush. Se `_validate_component()` em seguida lançar exceção (ex: `ComponentUnitMismatchError` ou `EntityNotFoundError`), a sessão contém estado "dirty" mas não há rollback explícito. O `session_dependency` fecha a sessão sem commit, então os dados não persistem, mas o comportamento depende do gerenciador de sessão.

**Impacto:** Baixo — em produção, sem rollback explícito, sessão fica em estado inconsistente até ser fechada. Com M-09 (rollback automático no `session_dependency`) ainda pendente, depende do comportamento de fechamento do SQLAlchemy.

**Correção sugerida:** Envolver operações de atualização em try/except com rollback:
```python
try:
    # modificações (components/operations/scalars)
    self._session.commit()
except Exception:
    self._session.rollback()
    raise
```
Relacionado a M-09 (reservado para TASK-008).

**Prioridade:** Baixa

---

#### L-19 — Duplicação do helper `_paginate` em 3 routers

**Arquivo:** `app/api/production.py:30-36`, `app/api/quality.py:28-34`, `app/api/costing.py:23-31`
**Problema:** Mesmo helper de paginação copiado em três arquivos. Se a fórmula mudar (ex: mudar para 1-indexed, mudar cálculo de `page`), precisa atualizar em 3 lugares.

**Correção sugerida:** Mover `_paginate` para `app/domain/common.py` ou `app/api/_helpers.py` como função reutilizável.

**Prioridade:** Baixa

---

### INFO (novos achados TASK-007)

#### I-23 — `PaginatedResponse` tem `from_attributes=True` desnecessário

**Arquivo:** `app/domain/common.py:13`
**Observação:** `ConfigDict(from_attributes=True)` só é usado quando Pydantic constrói modelo a partir de atributos de objeto ORM. Como `PaginatedResponse` é construído manualmente com `items` já serializados, `from_attributes` não tem efeito prático.

**Ação:** Pode ser removido para clareza. Sem impacto funcional.

---

#### I-24 — `RecipeOperation.work_center` não valida existência em `ProductionResource`

**Arquivo:** `app/services/production_service.py:264-272`
**Observação:** `RecipeOperation.work_center` é string livre (`VARCHAR(8)`). A criação de uma operation aceita qualquer work_center, mesmo que não exista em `ProductionResource`. Pode gerar receitas com operações em work centers inexistentes.

**Ação futura:** Validar work_center contra `ProductionResource.work_center` existente (ou documentar como forward-reference intencional).

---

### Análise de Segurança (TASK-007)

| Verificação | Resultado |
|------------|-----------|
| SQL injection | ✅ ORM parametrizado em todos os novos repositórios |
| Validação de entrada | ✅ Pydantic (Decimal `ge=0`, `decimal_places`, enums, `max_length`, `gt=0`) |
| Erros expõem stack traces | ✅ Exceções de domínio traduzidas (404/409/422) |
| Secrets no código | ✅ Nenhum |
| Logs sem dados sensíveis | ✅ Apenas IDs e códigos de domínio (recipe_code, order_id) |
| Cascade delete (novo) | ✅ `ProductionRecipe→components/operations` com `delete-orphan` |
| Integridade transacional | ⚠️ Padrão commit/rollback respeitado na maioria dos métodos; ver L-18 |
| `ComponentUnitMismatchError` (422) | ✅ Handler registrado em `main.py` |
| `EntityHasDependenciesError` em `delete_recipe` | ✅ Valida ProductionOrder dependente via select direto |
| `CostRecord` CHECK constraints (H-02) | ✅ Mantidos intactos; totals nunca divergem |

### Novos Testes Adicionados (TASK-007)

- `tests/unit/test_api_costing.py` — 15 testes (CRUD CO, summary, duplicate, not found, partial update, invalid order)
- `tests/unit/test_recipes_crud.py` — 15 testes (create, duplicate, unit mismatch, BOM+operations, dependency, delete, L-13 recipe em Order)
- Atualizações em `test_api_production.py` e `test_api_quality.py` para envelopes de paginação

**Total: 143 testes passando (era 113)**

---

## Análise de Segurança Consolidada

### ✅ Pontos Positivos

| Verificação | Resultado |
|------------|-----------|
| Secrets no código | ✅ Nenhum |
| .env no .gitignore | ✅ Excluído |
| .env.example sem credenciais | ✅ Placeholders usados |
| SQL injection | ✅ ORM parametrizado |
| Validação de entrada | ✅ Pydantic (Field, enums, ranges, Decimal constraints) |
| Stack traces em erros | ✅ Erros de domínio traduzidos |
| Logs sem dados sensíveis | ✅ Apenas códigos |
| CHECK constraints no DB | ✅ Enums validados no DB |
| Transaction boundaries | ✅ Services gerenciam commit/rollback |
| Thread safety | ✅ Double-check locking em connection.py |
| Cascade delete (Recipe→BOM) | ✅ `ProductionRecipe.components/operations` com `delete-orphan` |
| Consistência de unidade (M-11/L-05) | ✅ `ComponentUnitMismatchError` em create/update de Recipe |
| Dependências em delete_recipe | ✅ `EntityHasDependenciesError` valida ProductionOrder dependente |
| CO API + summary | ✅ 6 endpoints, variance calculado de forma segura (divisão por zero tratada) |

### ⚠️ Vulnerabilidades Identificadas

| Categoria | Severidade | Descrição |
|-----------|-----------|-----------|
| Autenticação | HIGH | Nenhum endpoint requer autenticação |
| Autorização | HIGH | Nenhum controle de acesso baseado em roles |
| Rate limiting | MEDIUM | Vulnerável a DoS |
| CORS | INFO | Não configurado (esperado para TASK-009) |
| HTTPS | INFO | Não forçado (depende de reverse proxy) |
| Input validation | MEDIUM | `update_result()` aceita `**params` sem validação |
| Business rules | MEDIUM | Sem validação de transições de estado |

---

## Análise de Performance

| Verificação | Resultado |
|------------|-----------|
| N+1 queries | ✅ `joinedload` usado em `get_with_material()`, `get_by_batch()` |
| Índices | ⚠️ Ausentes em `status` (orders, inspections) |
| Paginação | ✅ Implementada com `offset/limit` |
| Contagem eficiente | ✅ `func.count()` usado |
| Connection pooling | ✅ Configurado via `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` |
| Caching | ⚠️ Não implementado (pode ser adicionado posteriormente) |

---

## Análise de Testes

**Cobertura Atual (pós TASK-007):**
- 143 testes passando (era 113)
- Cobre: Materials, Production Orders, Batches, Resources, Quality Inspections, Non-Conformities, **Recipes CRUD**, **CostRecords API**, **resumo CO**, **L-13 recipe em Order**, paginação (envelope)
- **Não cobre:** transições de estado, erros de concorrência, paginação em sub-endpoints (M-17), performance N+1 (M-18)

**Testes Ausentes (atualizados):**
1. Transições de estado (ProductionOrder, QualityInspection) — reservado para M-14/M-15 em TASK-009
2. Concorrência (dois clientes criando mesma entidade)
3. Paginação real em sub-endpoints (M-17 ainda não corrigido)
4. Rate limiting (quando implementado) — TASK-009
5. Autenticação/autorização (quando implementado) — TASK-009
6. Performance N+1 (M-18) — requer integração com DB real

---

## Recomendações Prioritárias

### Para TASK-008 (Dashboard)

1. **M-17** — Corrigir paginação em sub-endpoints (envelope enganosamente não-paginado)
2. **M-18** — Adicionar `joinedload` em `get_all` (ou overrides específicos) para evitar N+1
3. **M-09** — Melhorar `session_dependency()` com rollback automático
4. **M-12** — Adicionar filtro `?active=all` em `list_materials()`
5. **L-09/L-10** — Adicionar índices em colunas `status`
6. **I-21** — Melhorar `/health` com verificação de banco
7. **L-17** — Validar `status` em `list_orders_by_status` contra `ProductionOrderStatus` enum
8. **L-19** — Extrair `_paginate` para helper comum em `app/domain/common.py`

### Para TASK-009 (Produção)

1. **H-01** — Implementar autenticação/autorização
2. **M-14/M-15** — Implementar máquinas de estado para ordens e inspeções
3. **M-16** — Adicionar rate limiting
4. **L-14** — Completar cascade delete (ProductionOrder→Batches)
5. **L-18** — Adicionar rollback explícito em `update_recipe`

---

## Conclusão (atualizada pós TASK-007)

**Estado Geral:** ✅ **BOM** — TASK-007 entregou funcionalidade sólida (CO API + Recipes CRUD + paginação padrão) com boa cobertura de testes (143 testes). Código limpo, arquitetura coerente.

**Achados principais TASK-007:** 0 CRITICAL, 0 HIGH, 2 MEDIUM, 3 LOW, 2 INFO.

**Pronto para Produção:** ⚠️ Não — requer TASK-008/009 para autenticação (H-01), correções de performance (M-17, M-18) e rollback automático de sessão (M-09).

**Bloqueante para Dashboard (TASK-008):** ⚠️ Parcial — M-17 (paginação sub-endpoints) e M-18 (N+1) devem ser corrigidos antes do dashboard consumir os endpoints de forma performática e previsível.

**Itens Anteriores Resolvidos:** 7 itens de auditorias anteriores tratadas na TASK-007 (H-02 Recipes, M-11 unit inconsistency, L-05, L-12 CO API, L-13 recipe eager load, parcialmente M-13 e L-14).

**Risco de Segurança:** ⚠️ Médio — ausência de autenticação permanece crítica (H-01 reservado para TASK-009). Nenhuma nova vulnerabilidade de segurança introduzida na TASK-007.

**Recomendação Final:** Prosseguir com TASK-008 (Dashboard) priorizando M-17 e M-18 (performance/correção de paginação), depois TASK-009 com autenticação/autorização.

---

## Auditoria TASK-008 — Dashboard + Correções de Performance

**Data:** 2026-08-12
**Revisor:** Auditor de Segurança/Qualidade (pós-implementação)
**Escopo:** TASK-008 — Correções M-09, M-12, M-17, M-18, L-09/L-10, L-17, L-19, I-21 + Dashboard (analytics, templates, router)

### Sumário

| Severidade | Quantidade |
|-----------|-----------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 0 |
| INFO | 2 |

---

### Itens Anteriores Resolvidos na TASK-008

| Item | Severidade | Status | Correção Aplicada |
|------|-----------|--------|-------------------|
| M-09 session_dependency sem rollback | MEDIUM | ✅ Corrigido | `session_dependency()` agora captura `Exception`, faz `rollback()` e re-lança |
| M-12 list_materials() só ativos | MEDIUM | ✅ Corrigido | Query param `?active=true\|false\|<omit>`; repo com `list_all()`, `list_inactive()`, `count_all()`, `count_inactive()` |
| M-17 Paginação falsa em sub-endpoints | MEDIUM | ✅ Corrigido | `skip`/`limit` adicionados em `BatchRepository.get_by_order()`, `ProductionResourceRepository.get_by_work_center()`, `ProductionRecipeRepository.get_active_for_material()`, `NonConformityRepository.get_by_inspection()` |
| M-18 N+1 queries em list_orders/list_recipes | MEDIUM | ✅ Corrigido | `ProductionOrderRepository.get_all()` com `joinedload(ProductionOrder.material, ProductionOrder.recipe)`. `ProductionRecipeRepository.get_all()` com `joinedload(ProductionRecipe.components, ProductionRecipe.operations)` |
| L-09 Índice ausente production_orders.status | LOW | ✅ Corrigido | `index=True` em `ProductionOrder.status` |
| L-10 Índice ausente quality_inspections.inspection_status | LOW | ✅ Corrigido | `index=True` em `QualityInspection.inspection_status` |
| L-17 list_orders_by_status aceita string não-enum | LOW | ✅ Corrigido | Path param tipado como `ProductionOrderStatus` (validação automática 422), service converte `.value` para repo |
| L-19 Duplicação _paginate em 3 routers | LOW | ✅ Corrigido | Função `paginate()` extraída para `app/domain/common.py`; 3 routers importam e usam a implementação compartilhada |
| I-21 /health sem verificação de banco | INFO | ✅ Corrigido | `GET /health` agora executa `SELECT 1` e retorna `{"status":"ok","database":"connected"}` ou 503 se DB indisponível |

### Dashboard Implementado

| Componente | Arquivo |
|-----------|--------|
| Analytics Service | `app/analytics/service.py` — `executive_kpis()`, `production_stats()`, `quality_stats()`, `cost_stats()`, `order_360()`, `order_status_distribution()`, `inspection_status_distribution()`, `cost_variance_by_order()` |
| Page Router | `app/api/dashboard.py` — `GET /dashboard/` (Home), `GET /dashboard/order-360` (Order 360°) |
| Data API Router | `app/api/dashboard.py` — `GET /api/dashboard/kpis`, `GET /api/dashboard/order-360/{order_number}`, `GET /api/dashboard/production-stats`, `GET /api/dashboard/quality-stats`, `GET /api/dashboard/cost-stats` |
| Templates | `templates/dashboard/base.html` (layout base), `templates/dashboard/home.html` (KPIs + gráficos Plotly), `templates/dashboard/order_360.html` (visão integrada) |

### INFO (novos achados TASK-008)

#### I-25 — Plotly.js via CDN sem SRI hash

**Arquivo:** `templates/dashboard/base.html:6`
**Observação:** O script Plotly.js é carregado de `cdn.plot.ly` sem atributo `integrity` (SRI hash). Em produção, um CDN comprometido poderia injetar scripts maliciosos.
**Ação futura:** Adicionar SRI hash ou servir de fonte local/confiável.

**Status TASK-008.1:** ✅ Corrigido — SRI hash `sha384-OLBgp1GsljhM2TJ+sbHjaiH9txEUvgdDTAzHv2P24donTt6/529l+9Ua0vFImLlb` adicionado com `crossorigin="anonymous"`.

---

#### I-26 — Templates servem dados como JSON inline (XSS mitigation OK)

**Arquivo:** `templates/dashboard/home.html`, `templates/dashboard/order_360.html`
**Observação:** Dados do analytics são serializados com `| tojson` e consumidos via `fetch()` — o Jinja2 `tojson` escapa automaticamente, prevenindo XSS. As queries de API são parametrizadas via SQLAlchemy ORM (sem SQL injection).
**Resultado:** Sem vulnerabilidades XSS ou injection nos templates. **Seguro.**

---

### Análise de Segurança (TASK-008)

| Verificação | Resultado |
|------------|-----------|
| SQL injection | ✅ ORM parametrizado em AnalyticsService |
| XSS em templates | ✅ `tojson` escapa; `fetch()` para dados dinâmicos |
| Secrets no código | ✅ Nenhum |
| Validação de entrada | ✅ Pydantic enums (L-17), query params tipados |
| Erros expõem stack traces | ✅ EntityNotFoundError retorna 404 genérico |
| CORS | N/A — sem endpoints de dados novos que requeiram CORS |
| Autenticação | ⚠️ Pendente (TASK-009) |
| CDN externo | ⚠️ Plotly.js sem SRI (I-25) |

### Novos Testes Adicionados (TASK-008)

- `tests/unit/test_dashboard.py` — 15 testes (8 AnalyticsService + 7 Dashboard API)
- Atualização em `tests/unit/test_api_production.py::test_health` (nova resposta)

**Total: 158 testes passando (era 143)**

### Arquivos Criados
- `app/analytics/service.py`
- `app/api/dashboard.py`
- `templates/dashboard/base.html`
- `templates/dashboard/home.html`
- `templates/dashboard/order_360.html`
- `tests/unit/test_dashboard.py`

### Arquivos Alterados
- `app/database/connection.py` — M-09 (rollback em session_dependency)
- `app/domain/common.py` — L-19 (helper paginate compartilhado)
- `app/domain/entities.py` — L-09/L-10 (índices status)
- `app/api/production.py` — L-17 (enum validation), L-19 (paginate shared), M-12 (active filter), M-17 (skip/limit pass-through)
- `app/api/quality.py` — L-19 (paginate shared), M-17 (skip/limit pass-through)
- `app/api/costing.py` — L-19 (paginate shared)
- `app/repositories/production_repository.py` — M-12 (list_all/inactive, count_all/inactive), M-17 (skip/limit), M-18 (joinedload)
- `app/repositories/quality_repository.py` — M-17 (skip/limit in get_by_inspection)
- `app/services/production_service.py` — M-12 (active param), L-17 (enum), M-17 (skip/limit)
- `app/services/quality_service.py` — M-17 (skip/limit)
- `app/main.py` — I-21 (health DB check), dashboard routers
- `tests/unit/test_api_production.py` — health test update

### Revalidação de Segurança
- Thread safety mantida (double-check locking em connection.py)
- Transactions: session_dependency agora faz rollback automático em exceptions
- Server defaults e CHECK constraints intactos
- Nenhuma nova superfície de ataque; Plotly.js via CDN documentado como I-25

### Conclusão

**Estado Geral:** ✅ **BOM** — TASK-008 corrigiu todos os 9 itens de auditoria pendentes (8 de recomendações + 1 extra) e implementou o Dashboard com analytics service, templates Jinja2 + Plotly.js e visão Order 360°.

**Pronto para Produção:** ⚠️ Não — requer TASK-009 para autenticação/autorização (H-01), rate limiting (M-16), transições de estado (M-14/M-15).

**Próxima Tarefa:** TASK-009 — Autenticação/Autorização + Rate Limiting + Máquinas de Estado

---

## Auditoria Consolidada Pós-TASK-008 — Análise Completa

**Data:** 2026-08-12
**Revisor:** Auditor de Segurança/Qualidade
**Escopo:** Codebase completo após TASK-008 (158 testes passando)

### Sumário Consolidado

| Severidade | Quantidade |
|-----------|-----------|
| CRITICAL | 0 |
| HIGH | 2 (H-01, H-02) |
| MEDIUM | 8 (M-14, M-15, M-16, M-19, + 4 corrigidos) |
| LOW | 6 (L-20, L-21, + 4 corrigidos) |
| INFO | 4 (I-25, I-26, I-27, I-28) |

**Total: 20 achados**

---

## HIGH

### H-01 — Ausência de Autenticação/Autorização (Persistente desde TASK-001)

**Arquivo:** `app/main.py` e todos os routers
**Problema:** Todos os endpoints REST (`/api/production/*`, `/api/quality/*`, `/api/costing/*`, `/api/dashboard/*`) estão publicamente acessíveis sem autenticação ou autorização. Qualquer usuário pode criar, modificar ou deletar materiais, ordens, batches, inspeções, cost records.

**Impacto:** Em produção, permitiria manipulação não autorizada de dados industriais críticos, incluindo exclusão de ordens de produção, alteração de receitas, criação de inspeções falsas.

**Correção sugerida:** Implementar autenticação JWT/OAuth2 + roles (admin, operator, viewer) em TASK-009. Proteger endpoints de write (POST/PUT/DELETE) com middleware de autorização.

**Prioridade:** Alta (bloqueante para produção)

---

### H-02 — `update_recipe` sem rollback explícito após modificar relacionamentos

**Arquivo:** `app/services/production_service.py:295-340`
**Problema:** O método `update_recipe` modifica `recipe.components = []` com `cascade="all, delete-orphan"`, marcando RecipeComponent antigos para deleção. Se `_validate_component()` em seguida lançar exceção (ex: `ComponentUnitMismatchError`), a sessão contém estado "dirty" mas não há rollback explícito dentro do método.

```python
if data.components is not None:
    recipe.components = []  # Marca componentes antigos para deleção
    for component in data.components:
        self._validate_component(component.component_material_id, component.unit)  # Pode lançar exceção
        recipe.components.append(...)  # Se exceção, componentes antigos já foram deletados
```

**Impacto:** Em caso de erro de validação após deleção de componentes, a sessão fica inconsistente. O `session_dependency` faz rollback automático (M-09), mas a operação parcial pode deixar dados corrompidos se o caller não tratar corretamente.

**Correção sugerida:** Envolver operações de atualização em try/except com rollback explícito, ou validar componentes antes de limpar a lista.

**Prioridade:** Alta

**Status TASK-008.1:** ✅ Corrigido — `update_recipe` agora envolve toda a modificação de componentes/operations em try/except com rollback explícito (`app/services/production_service.py:300-355`).

---

## MEDIUM

### M-14 — ProductionOrder sem validação de transição de estado

**Arquivo:** `app/domain/production/recipe.py`, `app/services/production_service.py`
**Problema:** `ProductionOrderBase` aceita qualquer `ProductionOrderStatus` sem validar transições de estado. Permite ir de `CREATED` direto para `COMPLETED` sem passar por `RELEASED` ou `IN_PROCESS`.

**Impacto:** Viola regras de negócio industriais. Ordens podem pular etapas obrigatórias.

**Correção sugerida:** Implementar máquina de estados no service:
```python
VALID_TRANSITIONS = {
    "CREATED": ["RELEASED"],
    "RELEASED": ["IN_PROCESS"],
    "IN_PROCESS": ["COMPLETED", "PARTIAL"],
    ...
}
```

**Prioridade:** Média (afeta fluxo de produção)

---

### M-15 — QualityInspection sem validação de transição de status

**Arquivo:** `app/services/quality_service.py:77-90`, `app/repositories/quality_repository.py:58-75`
**Problema:** `update_inspection_result()` aceita qualquer `InspectionStatus` sem validar transições. Permite ir de `PASSED` para `PENDING` ou de `FAILED` para `PASSED` sem re-inspeção.

**Impacto:** Viola fluxo de qualidade. Inspeções podem ser manipuladas para bypass de controles.

**Correção sugerida:** Validar transições permitidas no service ou repository.

**Prioridade:** Média

---

### M-16 — Ausência de Rate Limiting

**Arquivo:** `app/main.py`
**Problema:** Nenhum endpoint possui rate limiting. Vulnerável a ataques de negação de serviço (DoS) ou abuso de API.

**Impacto:** Em produção, um cliente malicioso pode sobrecarregar o servidor.

**Correção sugerida:** Adicionar middleware de rate limiting (ex: `slowapi` ou `fastapi-limiter`).

**Prioridade:** Média (relevante para produção)

---

### M-19 — Import no meio do arquivo `main.py`

**Arquivo:** `app/main.py:34-38`
**Problema:** Imports do dashboard estão após `app.include_router()` dos outros routers, quebrando convenção PEP 8 (todos os imports no topo).

```python
app.include_router(costing_router)

from app.api.dashboard import api_router as dashboard_api_router  # ← Import fora do topo
from app.api.dashboard import router as dashboard_router
```

**Impacto:** Código menos legível, potencialmente problemático em circular imports.

**Correção sugerida:** Mover imports para o topo do arquivo.

**Prioridade:** Média (qualidade de código)

**Status TASK-008.1:** ✅ Corrigido — Imports do dashboard movidos para o topo de `main.py` junto com os demais routers.

---

## LOW

### L-20 — `list_materials` com filtro `active=None` retorna todos (potencial confusão)

**Arquivo:** `app/api/production.py:35`, `app/services/production_service.py:62-68`
**Problema:** O parâmetro `active: Optional[bool] = Query(None, ...)` retorna **todos** os materiais (ativos + inativos) quando omitido. O valor padrão é `None`, mas o behavior pode ser contra-intuitivo para usuários que esperam apenas ativos por padrão.

**Impacto:** Baixo — API documentada, mas pode confundir clientes que não leem docs.

**Correção sugerida:** Considerar padrão `active=True` ou documentar claramente no OpenAPI.

**Prioridade:** Baixa

**Status TASK-008.1:** ✅ Corrigido — `active` padrão alterado de `None` para `True`. `GET /materials` sem query param agora retorna apenas ativos, mantendo retrocompatibilidade com o comportamento pré-M-12.

---

### L-21 — `order_360` não carrega recipe components/operations

**Arquivo:** `app/analytics/service.py:216-217`
**Problema:** `order_360()` carrega `recipe` via `self._session.get()`, mas não faz `joinedload` de `components` e `operations`. Se o template ou API consumir dados de BOM/roteiro, haverá N+1.

**Impacto:** Baixo — dados de recipe não são expostos no Order 360° atual, mas se for estendido, terá problema.

**Correção sugerida:** Adicionar `joinedload` ao carregar recipe, ou documentar que Order 360° não inclui BOM.

**Prioridade:** Baixa

**Status TASK-008.1:** ✅ Corrigido — `order_360()` agora carrega recipe com `joinedload(ProductionRecipe.components, ProductionRecipe.operations)`, eliminando futuros N+1 quando o BOM/roteiro for exposto.

---

## INFO

### I-27 — `AnalyticsService` sem commit/rollback

**Arquivo:** `app/analytics/service.py`
**Observação:** O `AnalyticsService` apenas lê dados (SELECT). Não há operações de escrita, então não precisa de commit/rollback. Todos os métodos são read-only.

**Resultado:** ✅ Correto — service de leitura não precisa gerenciar transações.

---

### I-28 — `recent_orders` em `production_stats` sem join material/recipe

**Arquivo:** `app/analytics/service.py:127-133`
**Observação:** A query de `recent_orders` não faz `joinedload` de `material` e `recipe`. Se o cliente precisar desses dados, haverá N+1.

**Impacto:** Baixo — dados de material/recipe não são expostos no `production_stats` atual.

**Ação futura:** Adicionar `joinedload` se necessário, ou documentar que `production_stats` não inclui detalhes de material.

---

## Análise de Segurança Consolidada (Pós-TASK-008)

### ✅ Pontos Positivos

| Verificação | Resultado |
|------------|-----------|
| SQL injection | ✅ ORM parametrizado em todos os repositories e AnalyticsService |
| Validação de entrada | ✅ Pydantic (Field, enums, ranges, Decimal constraints) |
| Stack traces em erros | ✅ Erros de domínio traduzidos (404/409/422) |
| Logs sem dados sensíveis | ✅ Apenas códigos (material_code, order_number) |
| CHECK constraints no DB | ✅ Enums validados no DB |
| Transaction boundaries | ✅ Services gerenciam commit/rollback |
| Thread safety | ✅ Double-check locking em connection.py |
| Cascade delete (Recipe→BOM) | ✅ `ProductionRecipe.components/operations` com `delete-orphan` |
| Paginação real (M-17) | ✅ skip/limit em sub-endpoints |
| N+1 queries (M-18) | ✅ joinedload em list_orders/list_recipes |
| Rollback automático (M-09) | ✅ session_dependency com rollback em exceptions |
| XSS em templates | ✅ `tojson` escapa; `fetch()` para dados dinâmicos |
| Secrets no código | ✅ Nenhum |
| .env no .gitignore | ✅ Excluído |
| .env.example sem credenciais | ✅ Placeholders usados |

### ⚠️ Vulnerabilidades Identificadas

| Categoria | Severidade | Descrição |
|-----------|-----------|-----------|
| Autenticação | HIGH | Nenhum endpoint requer autenticação (H-01) |
| Autorização | HIGH | Nenhum controle de acesso baseado em roles |
| Rate limiting | MEDIUM | Vulnerável a DoS (M-16) |
| Business rules | MEDIUM | Sem validação de transições de estado (M-14, M-15) |
| Transaction safety | MEDIUM | `update_recipe` sem rollback explícito (H-02) |
| CORS | INFO | Não configurado (esperado para TASK-009) |
| HTTPS | INFO | Não forçado (depende de reverse proxy) |
| CDN externo | INFO | Plotly.js sem SRI (I-25) |

---

## Análise de Performance (Pós-TASK-008)

| Verificação | Resultado |
|------------|-----------|
| N+1 queries | ✅ Resolvido com `joinedload` em `get_all()` |
| Índices | ✅ Presentes em `status` (orders, inspections), `material_code`, `order_number`, `inspection_lot`, `batch_number`, `resource_code`, `recipe_code` |
| Paginação | ✅ Implementada com `offset/limit` em todos os endpoints de listagem |
| Contagem eficiente | ✅ `func.count()` usado (O(1) memória) |
| Connection pooling | ✅ Configurado via `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` |
| Cache | ⚠️ Não implementado (pode ser adicionado posteriormente) |

**Resultado:** ✅ Performance otimizada. M-17 e M-18 corrigidos.

---

## Análise de Testes (Pós-TASK-008)

**Cobertura Atual:**
- 158 testes passando (era 143)
- Cobre: Materials, Production Orders, Batches, Resources, Quality Inspections, Non-Conformities, Recipes CRUD, CostRecords API, resumo CO, L-13 recipe em Order, paginação (envelope), AnalyticsService, Dashboard API
- Novos: `test_dashboard.py` (15 testes: 8 AnalyticsService + 7 Dashboard API)

**Testes Ausentes (atualizados):**
1. Transições de estado (ProductionOrder, QualityInspection) — reservado para M-14/M-15 em TASK-009
2. Concorrência (dois clientes criando mesma entidade)
3. Performance N+1 (M-18) — requer integração com DB real para verificar query count
4. Rate limiting (quando implementado) — TASK-009
5. Autenticação/autorização (quando implementado) — TASK-009
6. `update_recipe` com rollback após exceção (H-02)

---

## Recomendações Prioritárias

### Para TASK-009 (Autenticação/Autorização)

1. **H-01** — Implementar autenticação/autorização (bloqueante para produção)
2. **M-14/M-15** — Implementar máquinas de estado para ordens e inspeções
3. **M-16** — Adicionar rate limiting
4. **H-02** — Adicionar rollback explícito em `update_recipe` ou validar antes de deletar
5. **I-25** — Adicionar SRI hash ao Plotly.js ou servir localmente
6. **M-19** — Mover imports do dashboard para o topo de `main.py`
7. **L-20** — Documentar ou alterar padrão de `active=None` para `active=True`
8. **L-21** — Adicionar `joinedload` em `order_360()` se BOM/roteiro for exposto

---

## Conclusão Final (Pós-TASK-008.1)

**Estado Geral:** ✅ **BOM** — TASK-008 corrigiu 8 itens de auditoria pendentes + TASK-008.1 corrigiu mais 5 (H-02, M-19, L-20, L-21, I-25). Dashboard funcional com analytics, templates Jinja2 + Plotly.js, Order 360°.

**Correções TASK-008.1:**
| Item | Severidade | Status | Correção |
|------|-----------|--------|----------|
| H-02 update_recipe sem rollback | HIGH | ✅ | try/except com rollback explícito |
| M-19 imports no meio do main.py | MEDIUM | ✅ | Imports movidos para o topo |
| L-20 active=None confuso | LOW | ✅ | Padrão alterado para active=True |
| L-21 order_360 sem BOM | LOW | ✅ | joinedload em recipe components/operations |
| I-25 Plotly.js sem SRI | INFO | ✅ | SRI hash + crossorigin="anonymous" |

**Achados Restantes:** 0 CRITICAL, 1 HIGH (H-01 auth), 3 MEDIUM (M-14/M-15/M-16), 0 LOW, 2 INFO (I-27/I-28).

**Pronto para Produção:** ⚠️ Não — requer TASK-009 para autenticação (H-01), rate limiting (M-16), transições de estado (M-14/M-15).

**Segurança:** ✅ Todas as vulnerabilidades corrigíveis resolvidas. Autenticação permanece bloqueante.

**Performance:** ✅ Otimizada. N+1 resolvido com `joinedload` em todos os pontos críticos.

**Testes:** ✅ 158 testes passando.

**Risco de Segurança:** ⚠️ Médio — apenas H-01 (autenticação) permanece como bloqueante para produção.

**Recomendação Final:** Prosseguir com TASK-009 (Autenticação/Autorização + Rate Limiting + Máquinas de Estado).

---

## Auditoria TASK-009 — Autenticação/Autorização + Rate Limiting + Máquinas de Estado

**Data:** 2026-08-12
**Revisor:** Auditor de Segurança/Qualidade (pós-implementação)
**Escopo:** TASK-009 — JWT + RBAC (H-01), máquinas de estado (M-14/M-15), rate limiting (M-16), cascade delete (L-14).

### Sumário

| Severidade | Quantidade |
|-----------|-----------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 0 |
| INFO | 3 |

---

### Itens Anteriores Resolvidos na TASK-009

| Item | Severidade | Status | Correção Aplicada |
|------|-----------|--------|-------------------|
| H-01 Ausência de Autenticação/Autorização | HIGH | ✅ Corrigido | JWT HS256 (PyJWT) + RBAC por método HTTP (admin/operator/viewer); todos os routers `/api/*` protegidos via `require_api_access` |
| M-14 ProductionOrder sem validação de transição | MEDIUM | ✅ Corrigido | `app/domain/state_machine.py` + `ProductionService.update_order_status` + `PUT /orders/{id}/status`; `InvalidStateTransitionError` → 409 |
| M-15 QualityInspection sem validação de transição | MEDIUM | ✅ Corrigido | `validate_transition` em `QualityService.update_inspection_result`; `result_date` setado em estados de resultado |
| M-16 Ausência de Rate Limiting | MEDIUM | ✅ Corrigido | `RateLimitMiddleware` (sliding-window in-memory por IP, 429), configurável via `RATE_LIMIT_PER_MINUTE` |
| L-14 Ausência de Cascade Delete | LOW | ✅ Corrigido | `cascade="all, delete-orphan"` em `ProductionOrder.batches/cost_record`, `Batch.quality_inspection`, `QualityInspection.non_conformities` |

---

### INFO (novos achados TASK-009)

#### I-29 — `SECRET_KEY` default abaixo de 32 bytes

**Arquivo:** `app/security/tokens.py`, `.env.example`
**Observação:** O default `change-me-in-production` tem 23 bytes, abaixo do mínimo recomendado de 32 bytes para HS256 (RFC 7518 §3.2). PyJWT emite `InsecureKeyLengthWarning`.
**Ação:** Produção deve definir `SECRET_KEY` com ≥32 bytes aleatórios. Documentado no `.env.example`.

---

#### I-30 — Rate limiter in-memory não escala para múltiplos workers

**Arquivo:** `app/middleware/rate_limit.py`
**Observação:** O estado do limiter é mantido em memória por processo. Em deployment com múltiplos workers/containers, cada instância teria janela própria. Não usa `X-Forwarded-For` (atrás de reverse proxy, todos os clientes teriam o IP do proxy).
**Ação futura:** Para produção multi-worker, usar backend distribuído (Redis) ou configurar o proxy para repassar `X-Forwarded-For`.

---

#### I-31 — Dashboard HTML permanece público (read-only)

**Arquivo:** `app/api/dashboard.py`
**Observação:** As páginas `/dashboard/` e `/dashboard/order-360` são servidas sem autenticação (visões agregadas de analytics). Os endpoints de dados `/api/dashboard/*` por trás delas estão protegidos.
**Ação futura:** Adicionar login UI / proteção das páginas HTML em TASK-010+.

---

### Análise de Segurança (TASK-009)

| Verificação | Resultado |
|------------|-----------|
| Secrets no código | ✅ Nenhum; `.env` no `.gitignore`; placeholders no `.env.example` |
| Hashing de senha | ✅ PBKDF2-SHA256 (600k iterações) + salt aleatório + `hmac.compare_digest` |
| JWT | ✅ HS256 assinado; exp/iat; `sub` usado para lookup no DB |
| SQL injection | ✅ ORM parametrizado (UserRepository) |
| RBAC | ✅ viewer=read, operator=write, admin=delete; 403 em insuficiência; 401 sem token |
| Rate limiting | ✅ 429 em excesso; thread-safe (Lock); resetável em testes |
| Stack traces em erros | ✅ Erros de domínio traduzidos; HTTPException para 401/403 |
| Input validation | ✅ `UserCreate` (username pattern, password min 8); Pydantic enums |
| XSS/injection | N/A — sem novos templates |

### Novos Testes Adicionados (TASK-009)

- `tests/unit/test_auth.py` — 16 testes (login, me, register, RBAC viewer/operator/admin, 401/403)
- `tests/unit/test_state_machine.py` — 13 testes (transições válidas/inválidas, ciclos de vida PP-PI e QM)
- `tests/unit/test_rate_limit.py` — 4 testes (janela, isolamento por chave, reset)
- Atualização em `tests/unit/test_api_production.py` (endpoint status) e `tests/unit/test_api_quality.py` (transições estritas)

**Total: 190 testes passando (era 158)**

### Conclusão

**Estado Geral:** ✅ **BOM** — TASK-009 entregou autenticação/autorização, máquinas de estado e rate limiting com segurança e sem overengineering. As três vulnerabilidades restantes (H-01, M-14/M-15, M-16) foram resolvidas.

**Pronto para Produção:** ⚠️ Parcial — requer definir `SECRET_KEY` forte (≥32 bytes) e considerar rate limiter distribuído para multi-worker. Demais requisitos atendidos.

**Próxima Tarefa:** TASK-010 — Simulation Engine (`app/simulation/`) + seed de dados sintéticos.

---

## Auditoria TASK-009 — Autenticação/Autorização + Rate Limiting + Máquinas de Estado

**Data:** 2026-08-12
**Revisor:** Auditor de Segurança/Qualidade (pós-implementação)
**Escopo:** TASK-009 — todos os arquivos novos/modificados (auth, RBAC, state machine, rate limit, cascade, migration, scripts, testes).

### Sumário

| Severidade | Quantidade |
|-----------|-----------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 2 |
| LOW | 5 |
| INFO | 9 |

---

## MEDIUM

### M-20 — Rate limiter usa IP do proxy, não do cliente real

**Arquivo:** `app/middleware/rate_limit.py:52`
**Problema:** `request.client.host` retorna o IP do cliente direto. Atrás de reverse proxy (Nginx, Cloudflare Tunnel conforme `plano/02-arquitetura-infraestrutura.md`), esse valor é o IP do proxy — **todos os usuários compartilham o mesmo bucket de rate limit**.

**Impacto:**
- Um único usuário pode esgotar 60 req/min e bloquear todos os usuários atrás do proxy.
- Um atacante pode provocar DoS em todos os usuários com um único IP.
- Não há leitura de `X-Forwarded-For` / `X-Real-IP`.

**Correção sugerida:** Adicionar leitura de `X-Forwarded-For` com lista de proxies confiáveis, ou usar biblioteca com suporte a proxy headers (ex: `slowapi` com configuração adequada).

**Prioridade:** Média (relevante para produção com reverse proxy)

---

### M-21 — Memory leak no rate limiter (crescimento ilimitado de `_hits`)

**Arquivo:** `app/middleware/rate_limit.py:25,32-41`
**Problema:** `_hits: dict[str, deque[float]] = defaultdict(deque)`. Chaves (IPs) são adicionadas mas **nunca removidas**, mesmo quando a deque interna está vazia (todos os timestamps expirados). Com milhares de IPs únicos ao longo do tempo, o dicionário cresce indefinidamente.

**Impacto:**
- Servidor de longa duração acumula memória com chaves mortas.
- `reset()` só é chamado em testes; em produção, nunca.

**Correção sugerida:** Remover chaves vazias periodicamente ou implementar TTL global (ex: limpar chaves sem atividade nos últimos 5 minutos em background thread ou a cada N requisições).

**Prioridade:** Média (degradação gradual em produção)

---

## LOW

### L-22 — Timing side-channel em `authenticate` revela existência/atividade do usuário

**Arquivo:** `app/services/auth_service.py:40-47`
**Problema:** Short-circuit evaluation em `user is None or not user.is_active or not verify_password(...)`:
- Usuário não existe → raise imediato (~0.1ms, sem PBKDF2)
- Usuário existe mas inativo → raise imediato (~0.1ms, sem PBKDF2)
- Usuário existe e ativo (senha errada) → PBKDF2 roda (~300ms)

Diferença de ~3000x no tempo de resposta permite a um atacante distinguir "usuário existe e ativo" de "não existe", além de determinar o status de atividade.

**Impacto:** Enumeração de usernames e detecção de contas inativas.

**Correção sugerida:** Executar `verify_password` com hash dummy mesmo quando usuário não existe/inativo (constant-time login).

**Prioridade:** Baixa (requer precisão de timing; rate limiting atenua)

---

### L-23 — `require_api_access` pode lançar ValueError em role inválido do DB

**Arquivo:** `app/security/dependencies.py:88`
**Problema:** `UserRole(user.role)` levanta `ValueError` se o valor no DB não corresponder a nenhum enum (ex: dado corrompido ou inserção direta bypassando o ORM). A exceção não é capturada, resultando em HTTP 500 em vez de 403.

**Impacto:** Erro 500 em caso de dados inconsistentes, em vez de negação de acesso.

**Correção sugerida:** Envolver em try/except ou validar na camada de repository.

**Prioridade:** Baixa (CHECK constraint no DB previne na prática)

---

### L-24 — `verify_password` lê iterações do hash armazenado (risco de downgrade)

**Arquivo:** `app/security/passwords.py:28-33`
**Problema:** O formato armazenado é `pbkdf2_sha256$<iterations>$<salt>$<hash>`. `verify_password` usa `int(iterations)` do valor armazenado, não da constante `_ITERATIONS`. Se um atacante obtém acesso de escrita ao DB, pode reduzir iterações para facilitar brute-force offline.

**Impacto:** Se o DB é comprometido, o atacante pode baixar iterações e acelerar brute-force.

**Correção sugerida:** Validar `iterations >= _ITERATIONS` ou sempre usar `_ITERATIONS` do código (re-hash em migration).

**Prioridade:** Baixa (requer comprometimento prévio do DB)

---

### L-25 — `PARTIAL` é estado terminal sem transições de saída

**Arquivo:** `app/domain/state_machine.py:15`
**Problema:** `PRODUCTION_ORDER_TRANSITIONS` define `IN_PROCESS → {COMPLETED, PARTIAL}`, mas `PARTIAL` não tem transições de saída. Uma ordem parcialmente completada não pode ser fechada (`CLOSED`) nem completada (`COMPLETED`) via API.

**Impacto:** Ordens com status `PARTIAL` ficam "presas" sem possibilidade de progresso via API.

**Correção sugerida:** Adicionar `PARTIAL → {COMPLETED}` (ou `{COMPLETED, CLOSED}`) ao mapa, conforme fluxo de negócio esperado.

**Prioridade:** Baixa (nenhuma ordem atingirá PARTIAL enquanto não houver fluxo de produção parcial)

---

### L-26 — Cascade delete incompleto para `Batch`

**Arquivo:** `app/domain/entities.py:151-154`
**Problema:** `ProductionOrder.batches` tem `cascade="all, delete-orphan"`, e `Batch.quality_inspection` também. Porém, `ProductionConfirmation` (linha 195) e `MaterialConsumption` (linha 208) referenciam `batches.id` via FK **sem relationship e sem cascade**. Se uma ordem com batches com confirmações/consumos fosse deletada, o ORM tentaria deletar batches mas as FKs dessas tabelas bloqueariam com `IntegrityError`.

**Impacto:** Cascade delete falharia em cenários com dados de confirmação/consumo. Atualmente é inócuo pois não há endpoint de delete order nem API para criar confirmações/consumos.

**Correção sugerida:** Adicionar relationships `Batch.production_confirmations` e `Batch.material_consumptions` com `cascade="all, delete-orphan"` quando essas funcionalidades forem implementadas.

**Prioridade:** Baixa (inócuo no estado atual; latente)

---

## INFO

### I-29 — `SECRET_KEY` default abaixo do mínimo recomendado (HS256)

**Arquivo:** `app/security/tokens.py:14`, `.env.example`
**Observação:** `change-me-in-production` tem 23 bytes; RFC 7518 §3.2 recomenda ≥32 bytes para HS256. PyJWT emite `InsecureKeyLengthWarning`.
**Ação:** Produção deve definir `SECRET_KEY` com ≥32 bytes aleatórios. Documentado.

---

### I-30 — Rate limiter in-memory não escala multi-worker

**Arquivo:** `app/middleware/rate_limit.py`
**Observação:** Estado do limiter é por processo. Multi-worker/multi-container teriam janelas independentes. Documentado.
**Ação futura:** Backend distribuído (Redis) ou configuração de proxy para `X-Forwarded-For`.

---

### I-31 — Dashboard HTML permanece público

**Arquivo:** `app/api/dashboard.py:12`
**Observação:** `/dashboard/` e `/dashboard/order-360` servem KPIs agregados via renderização server-side sem autenticação. Os endpoints `/api/dashboard/*` por trás estão protegidos. Documentado.
**Ação futura:** Login UI / proteção das páginas HTML.

---

### I-32 — Claim `role` no JWT é embutido mas nunca consumido

**Arquivo:** `app/security/tokens.py:26`, `app/security/dependencies.py:58`
**Observação:** `create_access_token` inclui `"role"` no payload, mas `get_current_user` re-lê o role do DB via `UserRepository`, nunca do token. O role no token é redundante.
**Ação:** Manter como claim auditável (ou remover para reduzir payload). Sem impacto funcional.

---

### I-33 — Senha em `scripts/create_user.py` visível no `ps`

**Arquivo:** `scripts/create_user.py:26`
**Observação:** `--password` via CLI expõe a senha no `ps aux` do sistema. Limitação padrão de CLIs.
**Ação futura:** Aceitar leitura de stdin (`getpass`) ou arquivo.

---

### I-34 — Sem lockout de conta após N tentativas falhas de login

**Arquivo:** `app/services/auth_service.py:40-47`
**Observação:** Tentativas ilimitadas de login. Combinado com L-22 (timing) e rate limit global de 60/min, um atacante com múltiplos IPs pode tentar brute-force.
**Ação futura:** Contador de tentativas por usuário + lockout temporário (ex: 5 tentativas → 15 min lockout).

---

### I-35 — Sem teste de cascade delete (L-14)

**Arquivo:** `tests/unit/`
**Observação:** Nenhum teste verifica que `ProductionOrder → Batch → QualityInspection → NonConformity` cascade funciona. Latente porque não há endpoint de delete.
**Ação futura:** Adicionar teste unitário quando endpoint de delete for implementado.

---

### I-36 — Sem teste de rate limit via middleware (apenas unitário)

**Arquivo:** `tests/unit/test_rate_limit.py`
**Observação:** Testes cobrem `SlidingWindowRateLimiter` diretamente, mas não há teste de integração que verifica o middleware retorna 429 em excesso via `TestClient`.
**Ação futura:** Adicionar teste de integração.

---

### I-37 — Sem teste de token expirado

**Arquivo:** `tests/unit/test_auth.py`
**Observação:** Nenhum teste verifica que um token com `exp` passado retorna 401.
**Ação futura:** Adicionar teste com `ACCESS_TOKEN_EXPIRE_MINUTES=0` ou token manualmente expirado.

---

### I-38 — Sem teste de token para usuário deletado/inativado

**Arquivo:** `tests/unit/test_auth.py`
**Observação:** Nenhum teste verifica que um token válido retorna 401 se o usuário foi deletado ou teve `is_active=False` após a emissão do token.
**Ação futura:** Adicionar teste de revogação.

---

### I-39 — Sem teste de fluxo de desativação de usuário

**Arquivo:** `app/`
**Observação:** Não há endpoint para desativar/reativar usuário. `is_active` é settable apenas via DB direto. Documentado como feature futura.

---

## Análise Consolidada de Segurança (TASK-009)

### ✅ Pontos Positivos

| Verificação | Resultado |
|------------|-----------|
| Hashing de senha | ✅ PBKDF2-SHA256 (600k iterações) + salt 16 bytes + `hmac.compare_digest` |
| JWT | ✅ HS256 assinado; exp/iat; `sub` usado para lookup no DB (não confia no token) |
| RBAC | ✅ Hierarquia viewer < operator < admin; method-based; 403 em insuficiência |
| SQL injection | ✅ ORM parametrizado em todos os repositories (UserRepository) |
| Enumeração de username | ⚠️ Parcialmente mitigada (L-22: timing side-channel; sem lockout) |
| Rate limiting | ✅ 429 em excesso; thread-safe; aplicado a todos `/api/*` (incluindo login) |
| Validação de entrada | ✅ `UserCreate` (username pattern, password 8-128); Pydantic enums em state machine |
| Stack traces em erros | ✅ `InvalidStateTransitionError` → 409; `DomainError` → 400; `HTTPException` → 401/403 |
| Secrets | ✅ `.env` no `.gitignore`; `.env.example` com placeholders; nenhum segredo no código |
| Integridade transacional | ✅ `session_dependency` com rollback automático (M-09); services commit/rollback |
| Máquinas de estado | ✅ Transições validadas ANTES da mutação; estados terminais corretos |
| Cascade delete | ✅ Configuração ORM correta para chain principal (ordem → batches → inspeção → NCs) |
| CORS | N/A — sem endpoints cross-origin (dashboard HTML e API são same-origin) |
| SSRF | ✅ Não aplicável (sem chamadas HTTP outbound) |
| Path traversal | ✅ Não aplicável (sem operações de filesystem com input do usuário) |
| Logs | ✅ Sem dados sensíveis (usernames e roles são não-sensíveis; passwords nunca logados) |

### ⚠️ Vulnerabilidades Identificadas

| Categoria | Severidade | Descrição |
|-----------|-----------|-----------|
| Rate limiting (proxy) | MEDIUM | M-20 — Rate limit usa IP do proxy, não do cliente real |
| Rate limiting (memory) | MEDIUM | M-21 — Memory leak no dicionário de IPs |
| Timing attack | LOW | L-22 — Enumeração de usernames via tempo de resposta |
| Robustez | LOW | L-23 — ValueError em role inválido do DB → 500 |
| Defense in depth | LOW | L-24 — Iterações PBKDF2 lidas do hash armazenado |
| Regra de negócio | LOW | L-25 — PARTIAL terminal sem transições de saída |
| Integridade referencial | LOW | L-26 — Cascade não inclui ProductionConfirmation/MaterialConsumption |
| Configuração | INFO | I-29 — SECRET_KEY default < 32 bytes |
| Escalabilidade | INFO | I-30 — Rate limiter não escala multi-worker |
| Exposição de dados | INFO | I-31 — Dashboard HTML público |
| Design | INFO | I-32 — Claim `role` no token é redundante |
| CLI security | INFO | I-33 — Senha visível no ps (create_user.py) |
| Brute force | INFO | I-34 — Sem lockout de conta |
| Testes | INFO | I-35..I-39 — 5 gaps de cobertura de testes |

### Análise de Performance

| Verificação | Resultado |
|------------|-----------|
| PBKDF2 600k iterações | ✅ ~300ms por login (aceitável; OWASP recommended) |
| JWT encode/decode | ✅ O(1); HS256 rápido |
| Rate limiter | ⚠️ O(1) por request, mas memory leak (M-21) |
| `get_current_user` | ✅ 1 query (SELECT by username, indexed) |
| RBAC check | ✅ O(1); sem queries extras |

### Análise de Testes (pós TASK-009)

**Cobertura Atual:**
- 190 testes passando (era 158)
- Novos: `test_auth.py` (13), `test_state_machine.py` (11), `test_rate_limit.py` (4)
- Cobre: login, register, me, RBAC (viewer/operator/admin), state machines PP-PI e QM, rate limiter class

**Testes Ausentes:**
- I-35: Cascade delete (L-14)
- I-36: Rate limit via middleware (integração)
- I-37: Token expirado
- I-38: Token para usuário deletado/inativado
- I-39: Fluxo de desativação

### Consistência PP-PI / QM / CO

| Verificação | Resultado |
|------------|-----------|
| ProductionOrder status transitions | ✅ Fluxo linear: CREATED → RELEASED → IN_PROCESS → COMPLETED/PARTIAL → CLOSED → DELIVERED |
| QualityInspection status transitions | ✅ Fluxo: PENDING → IN_PROGRESS → PASSED/FAILED; FAILED → REWORK/SCRAP |
| State machine isolation | ✅ Validated at service layer; repository allows any mutation (correct layering) |
| Integration PP→QM→CO | ✅ Não alterada; state machines são ortogonais ao fluxo de integração |
| Cascade delete consistency | ⚠️ Parcial (L-26: `ProductionConfirmation`/`MaterialConsumption` não incluidos) |

---

## Conclusão (Pós-Auditoria TASK-009)

**Estado Geral:** ✅ **BOM** — TASK-009 resolveu as 3 vulnerabilidades pendentes de auditorias anteriores (H-01, M-14/M-15, M-16). Nenhum achado CRITICAL ou HIGH.

**Achados:** 0 CRITICAL, 0 HIGH, 2 MEDIUM, 5 LOW, 9 INFO.

**Pronto para Produção:** ⚠️ **Parcial** — requer:
1. Definir `SECRET_KEY` ≥ 32 bytes (I-29)
2. Resolver M-20 (rate limiter com proxy) antes de deploy com Cloudflare/Nginx
3. Considerar M-21 (memory leak) para servidores de longa duração

**Risco de Segurança:** ⚠️ **Baixo-Médio** — autenticação e RBAC implementados corretamente. Rate limiting funcional mas com limitações conhecidas (proxy, single-instance). Timing side-channel (L-22) é mitigado pelo rate limit.

**Recomendação Final:** Corrigir M-20 e M-21 antes de deploy em produção com reverse proxy. Os demais itens (LOW/INFO) podem ser tratados em tasks futuras sem bloqueio.

---

## Correções Pós-Auditoria TASK-009

**Data:** 2026-08-12
**Status:** Corrigido — todos os itens MEDIUM e LOW tratados + INFO acionáveis
**Validação:** `.venv/bin/pytest tests/` → **203 passed** (era 190); `compileall` OK; `npm run typecheck` OK; `npm run lint` OK; `alembic upgrade/downgrade` OK

| Item | Severidade | Status | Correção Aplicada |
|------|-----------|--------|-------------------|
| M-20 Rate limiter usa IP do proxy | MEDIUM | ✅ Corrigido | `_client_key()` lê `X-Forwarded-For`/`X-Real-IP` quando `TRUST_PROXY_HEADERS=true` (configurável via env); fallback para `client.host` |
| M-21 Memory leak no rate limiter | MEDIUM | ✅ Corrigido | `_cleanup()` remove chaves vazias/expiráveis a cada 60s (`_CLEANUP_INTERVAL_SECONDS`) |
| L-22 Timing side-channel em login | LOW | ✅ Corrigido | `authenticate` sempre roda `verify_password` com hash dummy quando usuário não existe (`_DUMMY_PASSWORD_HASH`) |
| L-23 ValueError em role inválido | LOW | ✅ Corrigido | `_resolve_role()` retorna `None` para role inválido; `require_roles`/`require_api_access` negam acesso (403) |
| L-24 Iterações PBKDF2 do hash armazenado | LOW | ✅ Corrigido | `verify_password` rejeita hash com `iterations < _MIN_ITERATIONS` (600k) |
| L-25 PARTIAL estado terminal | LOW | ✅ Corrigido | `PARTIAL → {COMPLETED}` adicionado ao mapa de transições |
| L-26 Cascade incompleto para Batch | LOW | ✅ Corrigido | `Batch.production_confirmations` e `Batch.material_consumptions` com `cascade="all, delete-orphan"` |
| I-29 SECRET_KEY < 32 bytes | INFO | ✅ Corrigido | Warning de log único quando SECRET_KEY < 32 bytes |
| I-32 Claim `role` redundante no JWT | INFO | ✅ Corrigido | `role` removido do payload; `create_access_token(subject)` |
| I-33 Senha no `ps` | INFO | ✅ Corrigido | `scripts/create_user.py` usa `getpass` quando `--password` omitido |
| I-34 Sem lockout de conta | INFO | ✅ Corrigido | Colunas `failed_attempts`/`locked_until` + lockout de 15 min após 5 falhas (HTTP 423); reset no login bem-sucedido |

### Testes Adicionados (I-35..I-39)

- `tests/unit/test_cascade.py` — 2 testes (cascade order→batches→inspection→NCs e →confirmations/consumptions)
- `tests/unit/test_rate_limit.py` — 5 novos testes (`_client_key` proxy headers, 429 via middleware, paths não-limitados)
- `tests/unit/test_auth.py` — 5 novos testes (lockout, reset counter, token expirado, token usuário inativo/deletado)
- `tests/unit/test_state_machine.py` — teste `PARTIAL → COMPLETED`

**Total: 203 testes (era 190)**

### Arquivos Alterados
- `app/middleware/rate_limit.py` — M-20/M-21
- `app/services/auth_service.py` — L-22/I-34 (constant-time + lockout)
- `app/security/dependencies.py` — L-23
- `app/security/passwords.py` — L-24
- `app/security/tokens.py` — I-29/I-32
- `app/domain/state_machine.py` — L-25
- `app/domain/entities.py` — L-26 (cascade) + I-34 (colunas lockout)
- `app/api/auth.py` — I-32
- `scripts/create_user.py` — I-33
- `.env.example` — TRUST_PROXY_HEADERS + comentário SECRET_KEY
- `database/migrations/versions/a1b2c3d4e5f6_lockout.py` — colunas `failed_attempts`/`locked_until`

### Revalidação de Segurança
- Login constant-time: PBKDF2 sempre executado (usuário inexistente usa hash dummy)
- Lockout de conta mitiga brute-force (423 após 5 falhas)
- Rate limiter resolve IP real atrás de proxy + sem memory leak
- `_resolve_role` garante 403 (não 500) para role corrompido
- Migração `a1b2c3d4e5f6` aplicada e revertida com sucesso

**Pendências restantes (INFO, documentadas como "ação futura"):**
- I-30: rate limiter distribuído multi-worker (requer Redis) — fora do escopo
- I-31: dashboard HTML público — login UI futura (TASK-010+)
