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

### TASK-010 — Simulation Engine + Seed de Dados Sintéticos
**Status:** DONE
- `app/simulation/`: `config`, `production_generator`, `quality_generator`, `cost_generator`, `engine`
- Gera master data (3 produtos acabados, 8 insumos, 3 receitas c/ BOM+roteiro, 5 recursos)
- Fluxo PP-PI→QM→CO: ordens → batches → inspeções → cost records; falha QM → custo de retrabalho
- Cenário "crisis" (causa e efeito: downtime → yield → qualidade → rework → custo)
- Scripts `generate_data.py` (`--months/--seed/--scenario`) e `reset_database.py`
- Bug corrigido: CHECK constraints `CostRecord` → tolerância `< 0.01` (float SQLite); migração `b2c3d4e5f6a7`
- 212 testes (era 203)

### TASK-010.1 — Correções Pós-Auditoria
**Status:** DONE
- L-27: reset com `--yes`/prompt · L-28: `from_env` valida env · L-29: `yield_std` removido
- L-30: commit master data (`months=0`) · L-31: clamp de parâmetros de inspeção
- L-32: custo de material derivado do BOM + preços unitários (PP-PI↔CO reconciliado)
- I-42..I-45: recipe_by_id O(1), to_decimal valida finito, add_months clampa dia, log mensal
- 216 testes (era 212)

### TASK-011 — Dashboard consumindo dados simulados + KPIs de tendência
**Status:** DONE
- `AnalyticsService.monthly_trend()` — agregação mensal (orders, volume_litros, pass_rate, custos planned/actual)
- `GET /api/dashboard/monthly-trend` — endpoint de dados protegido por `require_api_access`
- Gráficos de tendência no dashboard: Volume+Pass Rate (bar+line, eixo duplo) e Cost Planned vs Actual (lines)
- Demonstra cenário de crise (causa e efeito) ao longo dos meses
- 219 testes (era 216)

### TASK-011.1 — Correções Pós-Auditoria
**Status:** DONE
- L-33: fallback explícito para `actual_quantity=None` · L-34: filtro `planned_start.isnot(None)`
- I-51: loops de agregação consolidados · I-54: 3 testes de borda (fallback, sem inspeção, fronteira de ano)
- 222 testes (era 219)

### TASK-012 — Integração automática PP→QM→CO via eventos
**Status:** DONE
- `app/core/events.py` — `EventBus` in-memory (subscribe/publish/unsubscribe) + constantes de evento
- `app/services/integration.py` — handlers idempotentes registrados no startup:
  - `batch.created` → auto-cria QualityInspection PENDING (gatilho QM)
  - `order.completed` → auto-cria CostRecord com custos planejados (gatilho CO)
- `ProductionService.create_batch` e `update_order_status(COMPLETED/PARTIAL)` publicam eventos antes do commit (atomicidade)
- Handlers usam repositórios (flush); publisher commit — transação única
- Testes de qualidade atualizados para o fluxo automático
- 226 testes (era 222)

### TASK-012.1 — Correções Pós-Auditoria
**Status:** DONE
- M-22: `except Exception` com rollback em create_batch/update_order_status
- L-35: teste de idempotência (cost record não duplicado)
- L-36: documentação do placeholder sintético
- L-37: evento `order.completed` também para PARTIAL
- I-56/I-62: `EventBus.unsubscribe` + teste de falha no handler
- 228 testes (era 226)

### TASK-013 — Docker/deploy
**Status:** DONE
- `Dockerfile` — python:3.11-slim, uvicorn, expõe 8000
- `docker-compose.yml` — `db` (PostgreSQL 16) + `api` (migrações + uvicorn), healthcheck, volume
- `.dockerignore` — exclui legado Vite/React, docs, tests, .env
- `README.md` — reescrito (overview, stack, Docker/local, uso, estrutura, disclaimer)
- 228 testes (era 228 — sem mudança de código Python)

### TASK-013.1 — Correções Pós-Auditoria
**Status:** DONE
- M-23: credenciais do compose movidas para env vars (`${...}`)
- L-38: usuário não-root no Dockerfile · L-39: porta 5432 removida · L-40: SECRET_KEY obrigatório
- I-64: mem_limit 512m · I-65: seção Environment Variables no README · I-68: nota de produção
- 228 testes (era 228 — infraestrutura, sem código Python)

### Pendências Registradas (não executar agora)

**Automação externa** (`plano/11`) — **FORA DO ESCOPO deste projeto**:
- Integração n8n (alerta de quality failure)
- Integração Power BI
- Decisão: será tratada como atualização futura, separada do projeto atual.

**Decisões de infra (resolvidas antes do deploy):**
- I-84: ✅ pinar hadolint-action a commit SHA (`54c9adbab1582c2ef04b2016b760714a4bfde3cf`)
- I-86: ✅ mantida imagem base `slim` (glibc) — compatibilidade com C extensions (`psycopg2`, `numpy`, `pandas`, `uvloop`)

### Sequência de Execução (atualizada)

```
TASK-015 → API ProductionConfirmation + MaterialConsumption
TASK-016 → Indicadores avançados (OEE, Machine Utilization, Cost per Liter, Quality Cost)
TASK-017 → Telas por módulo (Production, Quality, Cost)
TASK-018 → Integração PP→QM→CO passo 6 (rework cost automático)
    ↓ (após concluídas as anteriores)
TASK-019 → Infraestrutura real (deploy VPS/Cloudflare/PostgreSQL central)
TASK-020 → CI/hardening (multi-stage build, hadolint, docker compose config)
```

### TASK-015 — API ProductionConfirmation + MaterialConsumption
**Status:** DONE
- Schema `MaterialConsumption` adicionado em `app/domain/production/batch.py`
- Repositórios `ProductionConfirmationRepository` + `MaterialConsumptionRepository`
- Service: `create_confirmation`/`list_confirmations_by_batch`, `create_consumption`/`list_consumptions_by_batch`
- Validação de unit vs `material.base_unit` (reusa `ComponentUnitMismatchError` → 422)
- 4 endpoints: `POST/GET confirmations`, `POST/GET consumptions` (com paginação)
- 236 testes (era 228). 8 testes novos

### TASK-016 — Indicadores avançados (OEE, Machine Utilization, Cost per Liter, Quality Cost)
**Status:** DONE
- `AnalyticsService.oee()` — Availability (planned/actual duration) × Performance (yield) × Quality (pass rate)
- `AnalyticsService.machine_utilization()` — % de recursos com produção
- `AnalyticsService.cost_per_liter()` — custo real por litro
- `AnalyticsService.quality_cost()` — variância de custo das ordens com inspeção FAILED
- Integrados no `executive_kpis()` + 4 novos KPIs no dashboard
- 241 testes (era 236). 5 testes novos

### TASK-016.1 — Correções Pós-Auditoria
**Status:** DONE
- L-42: clamp OEE em 100% (`min(1.0, ...)`)
- I-69: try/except com rollback em `create_confirmation`/`create_consumption`
- I-72: testes com valores esperados (`test_oee_expected_values`, `test_oee_clamped_at_100`)
- 243 testes (era 241)

### TASK-017 — Telas por módulo (Production, Quality, Cost)
**Status:** DONE
- Templates `production.html`, `quality.html`, `costing.html` (KPIs + tabelas)
- Rotas `/dashboard/production`, `/dashboard/quality`, `/dashboard/costing`
- Navegação no `base.html` com `active_nav` dinâmico + CSS de tabelas
- Production: volume, OEE, machine utilization, orders, contagens + recent orders
- Quality: pass/failure rate, NCs, pending + recent inspections
- Cost: planned/actual, variance, cost/liter, quality cost + cost by material
- 246 testes (era 243). 3 testes novos

### TASK-018 — Integração PP→QM→CO passo 6 (rework cost automático)
**Status:** DONE
- `EVENT_INSPECTION_FAILED` no EventBus
- `QualityService.update_inspection_result(FAILED)` publica evento (com rollback)
- Handler `_on_inspection_failed` + `_apply_rework_to_order` — aplica +8% rework ao cost record (idempotente)
- `order.completed` verifica inspeções FAILED prévias e aplica rework ao criar cost record
- 248 testes (era 246). 2 testes novos

### TASK-019 — Infraestrutura real (deploy VPS/Cloudflare/PostgreSQL central)
**Status:** DONE
- `docker-compose.prod.yml` — produção sem db local (reusa PostgreSQL central via `DATABASE_URL`)
- `deploy/nginx.conf` — exemplo de reverse proxy
- README — seção "Deployment (Production)" (Cloudflare, Nginx Proxy Manager, PostgreSQL central)
- 248 testes (sem mudança de código Python)

### TASK-020 — CI/hardening
**Status:** DONE
- `Dockerfile` — multi-stage build (builder venv → runtime não-root)
- `.github/workflows/ci.yml` — pytest + compileall + hadolint + docker compose config
- `.dockerignore` — exclui `.github`, `deploy`, `docker-compose*.yml`
- 248 testes (sem mudança de código Python)

### TASK-019.1/TASK-020.1 — Correções Pós-Auditoria
**Status:** DONE
- L-43: `deploy/nginx.conf` → `nginx.conf.example` (template explícito)
- I-82: healthcheck no `docker-compose.prod.yml`
- I-83: comentário SSL (Cloudflare) no nginx
- I-85: cache pip no CI
- Resolvido antes do deploy: I-84 (hadolint pinado a SHA), I-86 (mantido `slim`/glibc)

### TASK-014 — Documentação `docs/` + LICENSE
**Status:** DONE
- `docs/ARCHITECTURE.md`, `docs/BUSINESS_PROCESS.md`, `docs/DATA_MODEL.md`, `docs/SAP_MAPPING.md`, `docs/RUNBOOK.md`
- `LICENSE` (MIT)
- RUNBOOK inclui setup do domínio `erp.francorafael.com` (Cloudflare DNS/SSL/Tunnel)
- README atualizado com link para `docs/`

### TASK-021 — Validação final para deploy em produção
**Status:** IN PROGRESS

**Objetivo:** Validar a infraestrutura real de staging/produção após as correções de segurança, sem expor a API diretamente à internet.

**Checklist de execução:**
- [x] Configurar `SECRET_KEY` forte via secret manager ou variável protegida, sem usar valor de exemplo. (validado em código: falha na inicialização se ausente/fraco)
- [ ] Configurar `TRUSTED_PROXY_IPS` com o IP/CIDR real do proxy imediato. (depende do ambiente de deploy)
- [ ] Confirmar TLS/HTTPS no Cloudflare ou proxy reverso. (depende do ambiente de deploy)
- [ ] Confirmar que a porta `8000` não é acessível externamente e está limitada ao proxy/Tunnel. (configuração aplicada; validação externa pendente)
- [x] PostgreSQL externo provisionado na VPS: container `industrial-erp-postgres` (postgres:16), volume persistente `industrial_erp_postgres_data`, banco `industrial_erp`, usuário `industrial_erp`. (TASK-023)
- [x] Usuário da aplicação sem privilégios administrativos (`NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION`). (TASK-023)
- [x] Autenticação endurecida: `pg_hba.conf` com `scram-sha-256` para `local`/`127.0.0.1`/`::1`, backup `.bak` + `pg_reload_conf`. (TASK-023)
- [x] Porta `5432` limitada ao loopback `127.0.0.1` — verificado com `docker inspect`. (TASK-023)
- [ ] Executar `alembic upgrade head` contra o PostgreSQL real. (smoke test com SQLite: migrações aplicadas; dialeto PostgreSQL validado via offline SQL; contra o banco real pendente)
- [x] Criar o usuário admin inicial e validar login, expiração e revogação de token.
- [x] Validar `/health`, APIs protegidas, dashboard autenticado e bloqueio de acesso anônimo.
- [x] Integrar o envio do Bearer token no fluxo visual do dashboard (login/logout com cookie HttpOnly).
- [x] Validação de integração das configurações executada (2026-08-15): engine postgresql/psycopg2 com pool, Alembic via `DATABASE_URL`, guarda de `SECRET_KEY` (32+ bytes), segredos fora do Git — ver TASK-023.
- [ ] Executar smoke test PP-PI → QM → CO em PostgreSQL real. (validado em SQLite; infraestrutura real disponível — executar no staging)
- [ ] Documentar backup, restauração e procedimento de rollback do deploy. (procedimento base no Guia de Deploy; detalhar dump/restore do volume)

**Critérios de aceite:**
- [x] Deploy de staging validado localmente (smoke test) sem exposição direta da porta 8000.
- [ ] HTTPS funcional no domínio público.
- [ ] Proxy identifica clientes reais sem aceitar spoofing de headers.
- [x] Login, RBAC, dashboard e integrações PP-PI/QM/CO validados manualmente.
- [x] Evidências e comandos executados registrados em `auditoria.md`.

**Riscos:** Topologia do proxy, regras de firewall, credenciais PostgreSQL, TLS e fluxo de autenticação do frontend ainda dependem do ambiente de deploy.

### TASK-022 — Revisão da configuração de produção (PostgreSQL externo)
**Status:** DONE

**Objetivo:** Ajustar a configuração de staging/produção para usar o PostgreSQL
externo já existente na VPS (container `industrial-erp-postgres`) sem criar um
novo banco no compose.

Alterações:
- `docker-compose.prod.yml` — removido o serviço `db` e o volume `pgdata`; a API
  usa `network_mode: host` para alcançar o PostgreSQL da VPS publicado em
  `127.0.0.1:5432` (container em bridge não alcança serviço do host bindado em
  loopback); uvicorn bind em `127.0.0.1:8000` (sem exposição pública); removidos
  `depends_on` e healthcheck do db inexistente; `DATABASE_URL` e `SECRET_KEY`
  obrigatórios via variável de ambiente (sem fallback nem hardcode).
- `.env.example` — apenas placeholders:
  `DATABASE_URL=postgresql://industrial_erp:<password>@127.0.0.1:5432/industrial_erp`
  e `SECRET_KEY=` vazio; `POSTGRES_*` mantidos apenas para o compose dev
  (`docker-compose.yml`).
- `deploy/nginx.conf.example` — `proxy_pass http://127.0.0.1:8000` (antes `api:8000`).
- `README.md` e `docs/RUNBOOK.md` — seção de deploy atualizada (PostgreSQL
  externo + host networking).
- `.env` permanece fora do Git (`.gitignore` e `.dockerignore`); nenhum segredo
  em arquivos versionados.

Validação (sem deploy):
- `docker compose -f docker-compose.prod.yml config --quiet` (v2) → OK (dev OK)
- `npm run typecheck` → OK
- `pytest` → 257 passed
- `npm run build` → OK
- `python -m compileall app/ database/` → OK

### TASK-023 — Provisionamento do PostgreSQL externo na VPS
**Status:** DONE (infraestrutura real aplicada)

**Objetivo:** Instalar e endurecer o PostgreSQL 16 oficial do ambiente na VPS,
separado da aplicação, acessível somente localmente.

**Fonte de verdade:** Este bloco descreve a infraestrutura REAL já aplicada no
servidor. Qualquer alteração de código/deploy deve respeitar estes fatos.

**Container (infraestrutura oficial do banco — NÃO criar outro PostgreSQL):**
- Nome: `industrial-erp-postgres`
- Imagem: `postgres:16`
- Volume persistente: `industrial_erp_postgres_data` (nunca remover em deploy normal)
- Banco: `industrial_erp`
- Usuário da aplicação: `industrial_erp`
- Porta: `127.0.0.1:5432` (somente loopback — verificado com `docker inspect`)

Comando utilizado:
```bash
docker volume create industrial_erp_postgres_data

docker run -d \
  --name industrial-erp-postgres \
  --restart unless-stopped \
  -e POSTGRES_USER=industrial_erp \
  -e POSTGRES_PASSWORD='<senha forte>' \
  -e POSTGRES_DB=industrial_erp \
  -p 127.0.0.1:5432:5432 \
  -v industrial_erp_postgres_data:/var/lib/postgresql/data \
  postgres:16
```

Verificação do binding (resultado esperado `map[5432/tcp:[{127.0.0.1 5432}]]`):
```bash
docker inspect industrial-erp-postgres --format '{{.HostConfig.PortBindings}}'
```

**Banco e schema:**
- Banco: `industrial_erp`
- Schema criado: `industrial_erp` (`CREATE SCHEMA IF NOT EXISTS industrial_erp;`)
- Estrutura: `industrial_erp` (schema) + `public`
- O schema `industrial_erp` pertence ao usuário `industrial_erp`.

**Usuário da aplicação (sem privilégios administrativos):**
- Aplicado: `ALTER ROLE industrial_erp NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;`
- A aplicação deve usar somente os privilégios necessários para operar suas próprias tabelas/schema.

**Autenticação (scram-sha-256):**
- Arquivo: `/var/lib/postgresql/data/pg_hba.conf`
- Configuração endurecida (método `scram-sha-256`):
  ```
  local   all   all                         scram-sha-256
  host    all   all   127.0.0.1/32          scram-sha-256
  host    all   all   ::1/128               scram-sha-256
  ```
- Backup criado antes da alteração: `/var/lib/postgresql/data/pg_hba.conf.bak`
- Recarga após alteração:
  ```bash
  docker exec industrial-erp-postgres psql -U industrial_erp -d postgres -c "SELECT pg_reload_conf();"
  ```

**Secrets (nunca versionar):**
- `DATABASE_URL=postgresql://industrial_erp:<senha>@127.0.0.1:5432/industrial_erp`
  — senha real somente no ambiente de produção; `.env.example` apenas placeholders.
- `SECRET_KEY=<valor>` — gerado com `openssl rand -hex 32`; somente no ambiente de execução.

**Healthchecks:**
- API: `http://127.0.0.1:8000/health`
- PostgreSQL: `pg_isready`

**Teste de conexão esperado:**
```bash
docker exec industrial-erp-postgres pg_isready -U industrial_erp -d industrial_erp
# → accepting connections

docker exec industrial-erp-postgres \
  env PGPASSWORD='<senha>' \
  psql -h 127.0.0.1 -U industrial_erp -d industrial_erp \
  -c "SELECT current_user, current_database();"
# → industrial_erp | industrial_erp
```

**Persistência:**
- Dados em `industrial_erp_postgres_data` — não executar `docker volume rm`
  sem procedimento explícito de backup/recuperação.

**Regras de desenvolvimento (decorrentes da infra):**
- Não criar outro PostgreSQL. Não migrar para D1. Não usar SQLite em produção.
- Não colocar credenciais, `DATABASE_URL` real ou `SECRET_KEY` real no Git.
- Manter PostgreSQL 16 como banco oficial. Usar Alembic (`DATABASE_URL` como origem).
- Não expor `5432` nem `8000` publicamente. A API acessa o banco via `127.0.0.1:5432`
  (`network_mode: host`) e é alcançada somente pelo reverse proxy → `127.0.0.1:8000`.

**Validação aplicada:** binding loopback verificado; `pg_hba.conf` endurecido com
backup e reload; role sem superuser/createdb. Pendente: `alembic upgrade head` e
smoke test PP-PI→QM→CO contra o PostgreSQL real (TASK-021).

**Validação de integração (2026-08-15) — resultados:**
- `pytest` → **257 passed** (venv rebuild Python 3.11; o `.venv` original apontava
  para 3.10 com binário 3.11 — pacotes compilados não carregavam).
- `python -m compileall app/ database/ scripts/` → OK.
- `docker compose -f docker-compose.prod.yml config` (compose v2) → OK; o
  `docker-compose.yml` (dev) → OK.
- `npm run typecheck` → OK. `npm run build` bloqueado por permissão do
  `node_modules` (owned by root no ambiente local — sem relação com a configuração).
- Engine com `DATABASE_URL` do `.env` → dialeto `postgresql`, driver `psycopg2`,
  pool 5/10/recycle 3600 (app/database/connection.py:31).
- Alembic usa `DATABASE_URL` como origem; `alembic upgrade head` aplica as 4
  migrações e o modo offline gera SQL no dialeto PostgreSQL (`PostgresqlImpl`).
- Guarda de `SECRET_KEY` validada: com a chave dev (21 bytes) a inicialização
  falha (`RuntimeError: SECRET_KEY must contain at least 32 bytes`); com chave de
  32+ bytes o app inicializa (app/security/tokens.py:18).
- Segredos: `.env` ignorado pelo Git; apenas `.env.example` versionado (placeholders);
  nenhuma credencial rastreada.
- **Divergências encontradas no `.env` local** (corrigir na VPS, não é código):
  - usuário do banco `industrial_app` → deve ser `industrial_erp` (infra real);
  - `SECRET_KEY=GERE_UMA_CHAVE_SEGURA` (21 bytes) não passa na validação mínima
    de 32 bytes — gerar real com `openssl rand -hex 32`.
- **Não validável neste ambiente:** `alembic upgrade head`/`pg_isready`/teste TCP
  contra o PostgreSQL 16 real (sem Docker daemon nem servidor PostgreSQL local);
  permanece pendente na VPS (TASK-021).

### TASK-024 — Correções pós-auditoria (MEDIUM/LOW)
**Status:** PENDING

**Objetivo:** Corrigir os achados MEDIUM e LOW identificados na auditoria de
segurança de 2026-08-15 (ver seção "Relatório de Auditoria de Segurança" em
`auditoria.md`).

**Checklist de execução:**

**MEDIUM:**
- [ ] **MEDIUM-01 — CORS:** Avaliar necessidade de `CORSMiddleware`. Se o app for
  consumido exclusivamente via reverse proxy + dashboard HTML, documentar que não
  é necessário. Se houver SPA externo, adicionar `CORSMiddleware` com
  `allow_origins` restritos via variável de ambiente (`CORS_ORIGINS`).
- [ ] **MEDIUM-02 — Discrepância usuário PostgreSQL:** O `.env` local usa
  `industrial_app` mas TASK-023 documenta `industrial_erp`. Decisão:
  - Opção A: Atualizar TASK-023 e Guia de Deploy para referenciar `industrial_app`
    (se o banco já foi provisionado com esse usuário).
  - Opção B: Renomear o usuário no PG para `industrial_erp` e atualizar `.env` na VPS.
  - **Recomendação:** Opção A (mais simples, usuário já funciona sem superuser).

**LOW:**
- [ ] **LOW-01 — Rate limiter:** Documentar limitação (single-instance). Se o
  deploy for multi-instância, planejar migração para Redis. Por ora, adicionar
  nota no README sobre o comportamento em multi-worker.
- [ ] **LOW-02 — JWT sem revogação ativa:** Documentar comportamento (tokens
  válidos até expirar). Considerar reduzir `ACCESS_TOKEN_EXPIRE_MINUTES` para
  15 min em produção. Adicionar nota no docs/ARCHITECTURE.md.
- [ ] **LOW-03 — Cookie sem flag `Secure`:** Adicionar `secure=True` ao cookie
  `access_token` no dashboard. Como o reverse proxy termina TLS e o app vê HTTP,
  usar variável de ambiente `COOKIE_SECURE=true` ou detectar via
  `X-Forwarded-Proto`. Alternativa: documentar que o proxy deve adicionar
  `Strict-Transport-Security`.
- [ ] **LOW-04 — Logs sensíveis:** Adicionar nota no `app/core/logging.py`
  sobre a política de não logar senhas/tokens. Revisar services para confirmar
  que nenhum dado sensível é logado (atualmente OK: apenas IDs, codes, usernames).
- [ ] **LOW-05 — `with_for_update()` em SQLite:** Adicionar nota no README ou
  `docs/ARCHITECTURE.md` documentando que SQLite é apenas para dev/test e que
  race conditions em escrita concorrente são esperadas nesse modo. Em produção
  com PostgreSQL, os row locks funcionam corretamente.

**Documentos a atualizar:**
- `TASKS.md` (esta task)
- `docs/ARCHITECTURE.md` (notas sobre JWT, rate limiter, SQLite)
- `README.md` (nota sobre rate limiter single-instance)
- `.env.example` (adicionar `CORS_ORIGINS=` se aplicável, `COOKIE_SECURE=`)

**Validação:**
- `pytest` → manter 257+ testes passando
- `python -m compileall app/ database/` → OK
- `docker compose -f docker-compose.prod.yml config --quiet` → OK
- `npm run typecheck` → OK

**Critérios de aceite:**
- Todos os itens MEDIUM e LOW documentados ou corrigidos
- Nenhum novo achado CRITICAL ou HIGH introduzido
- Docs atualizados refletem o comportamento real

---

### Guia de Deploy — Oracle + Cloudflare + PostgreSQL

#### Passo 1 — PostgreSQL na VPS

Usar o PostgreSQL externo já existente na VPS (container `industrial-erp-postgres`),
sem criar outro banco (ver TASK-023):

```
Container:  industrial-erp-postgres  (postgres:16, restart unless-stopped)
Volume:     industrial_erp_postgres_data
Database:   industrial_erp
User:       industrial_erp
Porta:      127.0.0.1:5432 (somente loopback)
Schema:     industrial_erp
Auth:       scram-sha-256
```

`DATABASE_URL=postgresql://industrial_erp:<senha>@127.0.0.1:5432/industrial_erp`

#### Passo 2 — Segredos

Gerar a chave e montar o `.env` no servidor (fora do Git):

```bash
openssl rand -hex 32   # SECRET_KEY (32 bytes)
```

Criar `.env` na raiz do projeto no servidor:

```
DATABASE_URL=postgresql://industrial_erp:<senha>@127.0.0.1:5432/industrial_erp
SECRET_KEY=<valor-gerado>
ACCESS_TOKEN_EXPIRE_MINUTES=30
RATE_LIMIT_PER_MINUTE=60
TRUST_PROXY_HEADERS=true
TRUSTED_PROXY_IPS=127.0.0.1,::1
```

#### Passo 3 — Cloudflare (domínio `erp.francorafael.com`)

Opção A — Proxy DNS (orange cloud):
- Cloudflare → DNS → registro `erp` tipo `A` apontando para o IP público da VPS, com proxy laranja ativo.
- SSL/TLS → modo `Full (strict)` (exige certificado válido na origem) ou `Full`.

Opção B — Cloudflare Tunnel (sem portas públicas):
- Instalar `cloudflared` na VPS e criar o tunnel:
  ```bash
  cloudflared tunnel create erp
  cloudflared tunnel route dns erp erp.francorafael.com
  cloudflared service install
  ```
- Configurar ingress apontando para `http://localhost:8000`.

#### Passo 4 — Firewall (bloquear porta 8000)

Na Oracle OCI:
- Networking → Security Lists (ou NSG) → não liberar `8000` para `0.0.0.0/0`.
- Liberar apenas `80`/`443` (ou nada, se usar Tunnel).

Na VPS (ufw):

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

O compose roda a API com `network_mode: host` e bind em `127.0.0.1:8000`,
portanto a porta não fica acessível externamente mesmo sem regra.

#### Passo 5 — Deploy

```bash
cd simulador-erp-industrial
git pull
docker compose -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.prod.yml exec api python -m scripts.create_user --username admin --role admin
docker compose -f docker-compose.prod.yml exec api python -m scripts.generate_data --months 12 --scenario normal
```

#### Passo 6 — Smoke test

- `https://erp.francorafael.com/health` → 200
- `https://erp.francorafael.com/dashboard/login` → página de login
- Login, criação PP-PI → QM → CO e rollback.
- Acesso anônimo às APIs → 401.

#### Passo 7 — Backup e rollback

```bash
docker exec industrial-erp-postgres \
  pg_dump -U industrial_erp -d industrial_erp > backup-$(date +%F).sql
# rollback: git revert <commit> + docker compose up --build -d + restaurar dump
```

Regra: nunca remover o volume `industrial_erp_postgres_data` sem procedimento
explícito de backup/recuperação.

### Sequência Concluída

As tasks de implementação foram concluídas. A validação operacional de produção permanece pendente na `TASK-021`; a `TASK-022` ajustou a configuração de produção para o PostgreSQL externo da VPS; a `TASK-023` registrou o provisionamento real do PostgreSQL na VPS (container, volume, schema, role sem superuser, `pg_hba.conf` scram-sha-256, porta 5432 somente loopback). A auditoria de segurança de 2026-08-15 gerou a `TASK-024` (correções MEDIUM/LOW). Pendências resolvidas antes do deploy:
- **I-84** — hadolint-action pinado a commit SHA
- **I-86** — imagem base `slim` (glibc) mantida por compatibilidade

Fora do escopo (atualização futura, separada do projeto):
- **Automação externa n8n/Power BI** (`plano/11`)

Próximo passo: executar a `TASK-024` (correções pós-auditoria), depois a `TASK-021` em ambiente de staging — `alembic upgrade head`
e smoke test PP-PI→QM→CO contra o PostgreSQL real (`industrial-erp-postgres`) antes do deploy público.

---

## 9. Princípio central

O projeto deve evoluir de forma incremental:

```
Domínio → Dados → Serviços → API → Simulação → Analytics → Dashboard → Integrações → Infraestrutura
```

Cada etapa deve ser verificável antes da próxima.