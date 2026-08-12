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
