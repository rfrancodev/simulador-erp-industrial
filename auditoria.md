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
