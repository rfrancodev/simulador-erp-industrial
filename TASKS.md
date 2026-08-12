# TASKS.md — Industrial ERP Simulator

## 1. Objetivo

Este documento define o ciclo obrigatório de execução de cada tarefa do projeto:

```
Task → Test → Auto Review → Security Audit → Handoff
```

O desenvolvimento deve seguir os documentos da pasta `plano/` como fonte de verdade, respeitando a arquitetura Python-first, a integração conceitual PP-PI + QM + CO e a infraestrutura definida para o projeto.

---

## 2. Regras de execução

- Trabalhar somente no escopo da tarefa atual.
- Antes de implementar, identificar quais documentos de `plano/` são relevantes.
- Não criar arquitetura paralela sem necessidade.
- Não introduzir tecnologias não previstas sem justificar.
- Priorizar soluções simples e profissionais.
- Não afirmar que o sistema é SAP; usar conceitos inspirados em SAP.
- Dados industriais devem ser explicitamente sintéticos/simulados.
- Não alterar infraestrutura compartilhada sem autorização.
- Não criar novo PostgreSQL se a infraestrutura existente puder ser reutilizada.
- Toda alteração relevante deve permanecer versionável pelo Git.
- Nunca considerar uma tarefa concluída apenas porque o código foi escrito.

---

## 3. Ciclo obrigatório de cada tarefa

### Fase A — TASK

**A1. Entender o objetivo**

Antes de codificar:
- Ler a tarefa.
- Identificar o resultado esperado.
- Identificar dependências.
- Identificar documentos da pasta `plano/` relacionados.
- Verificar o estado atual do código.

**A2. Planejar**

Definir brevemente:
- arquivos que serão criados;
- arquivos que serão alterados;
- domínio afetado;
- endpoints/componentes envolvidos;
- banco de dados afetado;
- testes necessários;
- riscos conhecidos.

**A3. Implementar**

Implementar somente o necessário para satisfazer a tarefa.

Evitar:
- abstrações prematuras;
- duplicação desnecessária;
- frameworks adicionais;
- refatorações fora do escopo.

---

### Fase B — TEST

Toda tarefa deve possuir validação antes de ser considerada concluída.

**B1. Validação estática**

Executar quando aplicável:

Para TypeScript/React:
```bash
npm run typecheck
```

Para Python:
```bash
python -m compileall app
```
ou o mecanismo de validação definido posteriormente no projeto.

**B2. Testes automatizados**

Executar:
```bash
pytest
```
ou o comando oficial definido pelo projeto.

**B3. Build**

Executar quando houver alteração que afete build/deploy:
```bash
npm run build
```
ou o comando Python/Docker correspondente.

**B4. Teste funcional**

Quando aplicável:
- iniciar aplicação;
- executar fluxo afetado;
- verificar resposta;
- verificar persistência;
- verificar integração entre módulos.

**Critério:** Uma tarefa não pode avançar para Handoff se houver falha conhecida não justificada.

---

### Fase C — AUTO REVIEW

Após os testes, revisar a própria implementação.

**Checklist**

*Código*
- Código está legível?
- Responsabilidades estão bem separadas?
- Existe duplicação evitável?
- Existem funções excessivamente grandes?
- Existem abstrações desnecessárias?
- Nomes representam corretamente o domínio?

*Arquitetura*
- Respeita `04-arquitetura-software.md`?
- Respeita os limites PP-PI, QM e CO?
- Mantém baixo acoplamento?
- Evita dependências circulares?
- Eventos e integrações seguem `08-integracao-eventos.md`?

*Dados*
- Modelos estão coerentes com o domínio?
- Validações existem?
- Dados sintéticos estão identificados?
- Não existem valores críticos hardcoded sem justificativa?

*Produto*
- A implementação atende a tarefa?
- O comportamento é coerente com o fluxo industrial?
- O resultado é útil para demonstração/portfólio?

---

### Fase D — AUDITORIA DE SEGURANÇA

Antes do Handoff, executar uma revisão de segurança.

**D1. Secrets**
- Nenhuma senha no código.
- Nenhum token no código.
- Nenhuma API key no Git.
- `.env` não versionado.
- `.env.example` sem valores secretos.

**D2. API**
- Inputs são validados.
- Tipos e formatos são validados.
- Erros não expõem stack traces em produção.
- Endpoints sensíveis possuem proteção adequada.
- Não existe SQL construído diretamente com input do usuário.

**D3. Web**
- XSS.
- Injection.
- CORS excessivo.
- Uploads, quando existirem.
- Exposição de informações internas.
- Logs sem dados sensíveis.

**D4. Infraestrutura**
- Containers não expõem portas desnecessárias.
- Credenciais são fornecidas por ambiente.
- Banco não é exposto diretamente à Internet.
- Configurações de produção são separadas das de desenvolvimento.

**Regra:** Se existir vulnerabilidade de alto risco, a tarefa deve retornar para implementação antes do Handoff.

---

### Fase E — HANDOFF

Somente após Task, Test, Auto Review e Security Audit.

O Handoff deve registrar:

```
Task: <identificador>
Status: DONE / BLOCKED

Implementado:
- ...

Arquivos alterados:
- ...

Documentos consultados:
- ...

Testes executados:
- ...

Resultado:
- ...

Auto Review:
- ...

Security Audit:
- ...

Pendências:
- ...

Próxima tarefa sugerida:
- ...
```

---

## 4. Definition of Done

Uma tarefa está DONE somente quando:

- [ ] Implementação concluída.
- [ ] Testes executados.
- [ ] Testes aprovados.
- [ ] Auto Review concluído.
- [ ] Security Audit concluído.
- [ ] Documentação necessária atualizada.
- [ ] Nenhuma alteração fora do escopo ficou sem justificativa.
- [ ] Git está em estado compreensível.
- [ ] Handoff produzido.

---

## 5. Hierarquia dos documentos

Ao executar uma tarefa, utilizar esta ordem:

| # | Documento |
|---|-----------|
| 1 | `plano/01-visao-geral.md` |
| 2 | `plano/02-arquitetura-infraestrutura.md` |
| 3 | `plano/03-stack-tecnologica.md` |
| 4 | `plano/04-arquitetura-software.md` |
| 5 | documento de domínio correspondente (05, 06 ou 07) |
| 6 | `plano/08-integracao-eventos.md` |
| 7 | `plano/09-dashboard.md` |
| 8 | `plano/10-simulacao.md` |
| 9 | `plano/11-automacao.md` |
| 10 | `plano/12-estrutura-repositorio.md` |
| 11 | `TASKS.md` (este documento) |

Quando houver conflito entre documentos, não assumir uma solução silenciosamente. Registrar o conflito e solicitar decisão ou seguir a decisão mais recente explicitamente documentada.

---

## 6. Estratégia de uso de LLM

O projeto pode utilizar modelos diferentes conforme custo, velocidade e capacidade.

O modelo responsável pela tarefa deve:
- utilizar somente a capacidade necessária;
- evitar usar modelo de maior custo para tarefas triviais;
- preservar contexto por meio dos documentos;
- nunca assumir que um modelo anterior implementou corretamente;
- revisar o trabalho existente antes de continuar;
- produzir Handoff suficiente para outro modelo continuar.

A troca de modelo não deve alterar a arquitetura ou os padrões do projeto.

Os documentos são a fonte de continuidade entre modelos.

---

## 7. Execução por etapas

As tarefas devem ser divididas em pequenas unidades verificáveis.

Exemplo:

```
TASK-001: Preparar estrutura base
    ↓ TEST → AUTO REVIEW → SECURITY AUDIT → HANDOFF

TASK-002: Modelar Material
    ↓ TEST → AUTO REVIEW → SECURITY AUDIT → HANDOFF

TASK-003: Criar Recipe
    ↓ TEST → AUTO REVIEW → SECURITY AUDIT → HANDOFF

TASK-004: Criar Production Order
    ↓ TEST → AUTO REVIEW → SECURITY AUDIT → HANDOFF

TASK-005: Criar relação Production Order → Batch
    ↓ TEST → AUTO REVIEW → SECURITY AUDIT → HANDOFF
```

Evitar tarefas gigantes como "Implementar todo o módulo PP-PI."

---

## 8. Histórico de Tarefas

### TASK-001/002 — Estrutura base + Domínio PP-PI
**Status:** DONE
- Estrutura de diretórios, FastAPI app, configuração de projeto
- Entities, schemas Pydantic, repositories, testes unitários

### TASK-003 — Correções Pós-Auditoria
**Status:** DONE
- 16/17 itens corrigidos: count() no DB, CHECK constraints, validação material/recipe,
  whitelist, model_validator, dependências, utcnow→UTC, testes, logging, exceptions, etc.
- 56 testes (era 23)

### TASK-004 — Database Connection + Alembic
**Status:** DONE
- `connection.py` com thread safety (double-check locking), pool config, session_scope
- Migração inicial Alembic, server defaults, render_as_batch SQLite
- 12/12 itens de auditoria corrigidos. 57 testes

### TASK-005 — REST API Endpoints PP-PI
**Status:** DONE
- CRUD endpoints: Materials, ProductionOrders, Batches, Resources
- ProductionService com transações, validação Pydantic, erros de domínio
- Nenhum item de segurança encontrado

### TASK-006 — QM Service + REST API Endpoints
**Status:** DONE
- QualityInspection, NonConformity endpoints
- Whitelist de campos mutáveis, validação de enums
- Nenhum item de segurança encontrado. 113 testes (auditoria consolidada)

### TASK-007 — CO Service + Recipes API + Paginação
**Status:** DONE
- CostRecord CRUD, CostSummary, Recipes CRUD com BOM e roteiro
- PaginatedResponse genérico, validação ComponentUnitMismatch
- 2 MEDIUM, 3 LOW encontrados na auditoria. 143 testes

### TASK-008 — Dashboard + Correções de Performance
**Status:** DONE
- M-09, M-12, M-17, M-18, L-09/L-10, L-17, L-19, I-21 (8 itens de auditoria)
- Dashboard: AnalyticsService com 8 métodos de agregação
- Templates Jinja2 + Plotly.js: home executivo + Order 360°
- 5 endpoints de dados + 2 páginas HTML
- 158 testes (era 143). 0 CRITICAL, 0 HIGH, 0 MEDIUM, 0 LOW, 2 INFO

### TASK-009 — Autenticação/Autorização + Rate Limiting + Máquinas de Estado
**Status:** DONE
- H-01: JWT (PyJWT HS256) + RBAC (admin/operator/viewer) por método HTTP
  - `User` entity, hashing PBKDF2 (stdlib), login/me/register, `require_api_access`
  - Todos os routers `/api/*` protegidos; `/dashboard/` HTML público (documentado)
- M-14/M-15: máquinas de estado para ProductionOrder e QualityInspection
  - `app/domain/state_machine.py` + `InvalidStateTransitionError` (409)
  - `PUT /orders/{id}/status` + validação de transição em `update_inspection_result`
- M-16: rate limiting in-memory (sliding window, 429) via middleware
- L-14: cascade delete `ProductionOrder→batches/cost_record`, `Batch→inspection`, `Inspection→non_conformities`
- 190 testes (era 158). 0 CRITICAL, 0 HIGH, 0 MEDIUM, 0 LOW, 3 INFO

### TASK-009.1 — Correções Pós-Auditoria
**Status:** DONE
- M-20/M-21: rate limiter com `X-Forwarded-For`/`X-Real-IP` (TRUST_PROXY_HEADERS) + cleanup anti-memory-leak
- L-22: login constant-time (hash dummy) · L-23: `_resolve_role` (403 em role inválido)
- L-24: min iterations PBKDF2 · L-25: `PARTIAL → COMPLETED` · L-26: cascade confirmations/consumptions
- I-29: warning SECRET_KEY fraco · I-32: claim `role` removido · I-33: getpass CLI · I-34: lockout de conta (423)
- 203 testes (era 190). Migração `a1b2c3d4e5f6` (failed_attempts/locked_until)

### Próxima: TASK-010 — Simulation Engine + Seed de Dados Sintéticos

---

## 9. Princípio central

O projeto deve evoluir de forma incremental:

```
Domínio → Dados → Serviços → API → Simulação → Analytics → Dashboard → Integrações → Infraestrutura
```

Cada etapa deve ser verificável antes da próxima.
