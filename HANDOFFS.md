# HANDOFFS — Industrial ERP Simulator

This file documents the completion of each task, serving as the source of truth for model transitions.

---

## TASK-027 — Auto-conclusão da Production Order no fim da produção (PP → CO)

**Status:** DONE

**Data:** 2026-08-19

**IMPLEMENTADO:**
- `EVENT_BATCH_COMPLETED` em `app/core/events.py`.
- `ProductionService.update_batch_status` publica o evento quando o destino é `COMPLETED`
  **ou** `SCRAP` (estados terminais para fins de fim de produção), na mesma transação.
- Handler `_auto_complete_order` em `app/services/integration.py` (padrão dos handlers existentes):
  - atua somente em ordens `RELEASED`/`IN_PROCESS`/`PARTIAL`;
  - produção encerrada somente quando **nenhum** batch está em `CREATED`/`IN_PRODUCTION`/`REWORK`;
  - avança a ordem até `COMPLETED` reutilizando `PRODUCTION_ORDER_TRANSITIONS` (sem nova máquina de estados);
  - `actual_start` preenchido somente se vazio; `actual_end` ao concluir;
  - reutiliza `_auto_create_cost_record` (idempotente) — preserva rework/costing.

**ARQUIVOS ALTERADOS:**
- `app/core/events.py`, `app/services/production_service.py`, `app/services/integration.py`
- `tests/unit/test_integration.py`
- `TASKS.md`, `HANDOFFS.md`

**TESTES:**
```
290 passed (era 283; +7)
```

**VALIDAÇÃO:**
- Último batch COMPLETED → ordem `COMPLETED` + `actual_end` + CostRecord criado.
- Dois batches: ordem só conclui após o último; primeiro batch não conclui.
- Último batch SCRAP → ordem concluída.
- Ordem `CREATED` + batch COMPLETED → permanece `CREATED`.
- Batch REWORK pendente → ordem não concluída; após rework→COMPLETED, conclui.
- Falha no handler → rollback total (batch `IN_PRODUCTION`, ordem `IN_PROCESS`, sem CostRecord).
- Reprocessamento do evento → idempotente (sem CostRecord duplicado, `actual_end` inalterado).
- `compileall app/` OK. Nenhuma migration; QM, Dashboard e infra inalterados.

**PRÓXIMA TAREFA:**
TASK-021 — validação operacional em staging (alembic upgrade head + smoke test PP-PI→QM→CO contra PostgreSQL real).

---

## TASK-026 — Gate de qualidade vinculado ao ciclo de vida do Batch (QM no COMPLETED)

**Status:** DONE

**Data:** 2026-08-19

**IMPLEMENTADO:**
- `BatchNotCompletedError` em `app/core/exceptions.py` + handler **409** em `app/main.py`.
- `QualityService.update_inspection_result`: resultados finais (`PASSED`/`FAILED`/`REWORK`/`SCRAP`)
  exigem `batch.status == COMPLETED`; `IN_PROGRESS` continua permitido — gate QM no batch produzido.
- Fecha o fluxo `Batch → Quality Inspection` do plano/06 (inspeção só após produção).

**ARQUIVOS ALTERADOS:**
- `app/core/exceptions.py`, `app/main.py`, `app/services/quality_service.py`
- `tests/unit/test_api_quality.py`, `tests/unit/test_state_machine.py`, `tests/unit/test_integration.py`
- `TASKS.md`, `HANDOFFS.md`

**TESTES:**
```
283 passed (era 280; +3: rejeição em CREATED, rejeição em IN_PRODUCTION, state machine)
```

**VALIDAÇÃO:**
- End-to-end via TestClient: `PASSED` em batch `CREATED` → 409; `IN_PRODUCTION` → 409; `COMPLETED` → 200.
- Nenhuma migration; Production Order, Costing, Dashboard e infra inalterados.

**PRÓXIMA TAREFA:**
TASK-021 — validação operacional em staging (alembic upgrade head + smoke test PP-PI→QM→CO contra PostgreSQL real).

---

## TASK-025 — Ciclo de vida do Batch via API (status lifecycle) + fix deadlock

**Status:** DONE

**Data:** 2026-08-19

**IMPLEMENTADO:**
- **Máquina de estados:** `BATCH_TRANSITIONS` em `app/domain/state_machine.py` —
  `CREATED → IN_PRODUCTION → {COMPLETED | REWORK | SCRAP}`; `REWORK → {IN_PRODUCTION | SCRAP}`;
  `COMPLETED` e `SCRAP` são estados terminais.
- **Schema:** `BatchStatusUpdate` (tipado com `BatchStatus`) em `app/domain/production/batch.py`.
- **Repository:** `BatchRepository.update_status(id, status)` em `app/repositories/production_repository.py`.
- **Service:** `ProductionService.update_batch_status(id, status)` — valida a transição via
  state machine, aplica `completed_at` ao completar, limpa `completed_at` em estados não
  concluídos, persiste e retorna o Batch. **Não altera** `actual_quantity`/`yield_percent`.
- **Criação:** `create_batch` usa `BatchStatus.CREATED.value` (era o literal `"CREATED"`).
- **Endpoint:** `PATCH /api/production/batches/{batch_id}/status` (auth/erros/dependências padrão).
- **Fix deadlock:** `threading.Lock()` → `threading.RLock()` em `app/database/connection.py`
  (`get_session()` reentra no lock via `get_engine()`).
- **Eventos:** `EVENT_BATCH_CREATED` mantido; nenhum evento novo (batch completed não implementado).

**ARQUIVOS ALTERADOS:**
- `app/domain/state_machine.py`, `app/domain/production/batch.py`
- `app/repositories/production_repository.py`, `app/services/production_service.py`
- `app/api/production.py`, `app/database/connection.py`
- `tests/unit/test_state_machine.py`, `tests/unit/test_batch.py`, `tests/unit/test_api_production.py`
- `TASKS.md`, `HANDOFFS.md`

**TESTES:**
```
280 passed (era 258; +22: state machine, repository e API de status de batch)
```

**VALIDAÇÃO:**
- Endpoint validado via TestClient: `CREATED → IN_PRODUCTION → COMPLETED` (200, `completed_at` preenchido);
  revert `COMPLETED → IN_PRODUCTION` → 409; `SCRAP → IN_PRODUCTION` → 409; batch inexistente → 404.
- `/openapi.json` inclui `PATCH /api/production/batches/{batch_id}/status`.
- Nenhuma migration necessária (colunas `status`/`completed_at` já existiam).

**PRÓXIMA TAREFA:**
TASK-021 — validação operacional em staging (alembic upgrade head + smoke test PP-PI→QM→CO contra PostgreSQL real).

---

## TASK-024 — Correções pós-auditoria (MEDIUM/LOW)

**Status:** DONE

**Data:** 2026-08-15

**IMPLEMENTADO:**
- **MEDIUM-01 (CORS):** documentado como não necessário (dashboard server-side render + API mesma origem via proxy) — nota em `docs/ARCHITECTURE.md` e `.env.example`.
- **MEDIUM-02 (usuário PG):** auditado o PG real (3 roles). `industrial_app` (não-superuser) é o usuário real da aplicação; `industrial_erp` e `industrial_admin` são SUPERUSER. Docs (TASK-023, Guia de Deploy, README, RUNBOOK, `.env.example`) alinhados para `industrial_app`.
- **LOW-01 (rate limiter):** documentado single-instance (README + ARCHITECTURE).
- **LOW-02 (JWT stateless):** documentado em ARCHITECTURE.
- **LOW-03 (cookie Secure):** `COOKIE_SECURE` env var em `app/api/dashboard.py`; compose prod default `true`; teste `test_dashboard_login_cookie_secure_flag`.
- **LOW-04 (logs):** política documentada na docstring de `app/core/logging.py`.
- **LOW-05 (with_for_update SQLite):** nota em ARCHITECTURE.

**ARQUIVOS ALTERADOS:**
- `app/api/dashboard.py`, `app/core/logging.py`, `tests/unit/test_dashboard.py`
- `.env.example`, `docker-compose.prod.yml`, `docs/ARCHITECTURE.md`, `docs/RUNBOOK.md`, `README.md`
- `TASKS.md`, `auditoria.md`, `HANDOFFS.md`

**ACHADO ADICIONAL:**
- Role `industrial_erp` é a **bootstrap superuser** do PG real; a remoção de SUPERUSER **não é
  aplicável** (`DETAIL: The bootstrap user must have the SUPERUSER attribute.`) — ver TASK-023.
  Mitigação: a aplicação usa `industrial_app` (não-superuser).

**TESTES:**
```
258 passed (era 257; +1 teste cookie Secure)
```
- `compileall` OK · `docker compose -f docker-compose.prod.yml config` OK · `typecheck` OK

**PRÓXIMA TAREFA:**
TASK-021 — validação operacional em staging (alembic upgrade head + smoke test PP-PI→QM→CO contra PostgreSQL real).

---

## TASK-023 — Provisionamento do PostgreSQL externo na VPS (infra real)

**Status:** DONE

**Data:** 2026-08-15

**IMPLEMENTADO (infraestrutura real aplicada na VPS):**
- Container `industrial-erp-postgres` (imagem `postgres:16`, `restart unless-stopped`), separado da aplicação.
- Volume persistente `industrial_erp_postgres_data` (não remover em deploy normal).
- Banco `industrial_erp`, usuário da aplicação `industrial_erp`, schema `industrial_erp` (além do `public`).
- Binding `127.0.0.1:5432` (somente loopback) — verificado com `docker inspect`; NÃO exposto à Internet.
- Role da aplicação endurecida: `ALTER ROLE industrial_app NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;`.
- Autenticação `scram-sha-256` no `pg_hba.conf` (`local`/`127.0.0.1`/`::1`), com backup `.bak` + `pg_reload_conf`.
- A API usa `network_mode: host` e bind `127.0.0.1:8000` — acessível somente via reverse proxy/Cloudflare.
- `DATABASE_URL=postgresql://industrial_app:<senha>@127.0.0.1:5432/industrial_erp` e `SECRET_KEY` (≥32 bytes) somente via ambiente.

**BOOTSTRAP SUPERUSER (2026-08-19) — remoção de SUPERUSER de `industrial_erp` NÃO aplicável:**
- `industrial_erp` é a **bootstrap superuser** do cluster (criada no bootstrap do container).
- Executado como `industrial_admin`, `ALTER ROLE industrial_erp NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION`
  falha com `permission denied to alter role` / `DETAIL: The bootstrap user must have the SUPERUSER attribute.`
- O PostgreSQL não permite remover SUPERUSER da bootstrap user sem recriar o cluster (fora de escopo).
- **Mitigação registrada:**
  1. A aplicação utiliza `industrial_app`, não `industrial_erp`.
  2. `industrial_app` não possui atributos administrativos.
  3. `industrial_erp` permanece exclusivamente como bootstrap/admin role.
  4. `industrial_admin` permanece como role administrativa separada.
  5. Não é necessária migration de banco.

**VALIDAÇÃO DE INTEGRAÇÃO (2026-08-15):**
- `pytest` → **257 passed** (venv rebuilt para Python 3.11; o `.venv` original apontava binário 3.11 com pacotes de 3.10).
- `python -m compileall app/ database/ scripts/` → OK.
- `docker compose -f docker-compose.prod.yml config` (compose v2) → OK; `docker-compose.yml` (dev) → OK.
- `npm run typecheck` → OK. `npm run build` bloqueado por permissão do `node_modules` (owned by root no ambiente local — sem relação com a configuração).
- Engine com `DATABASE_URL` do `.env` → dialeto `postgresql`, driver `psycopg2`, pool 5/10/recycle 3600.
- Alembic usa `DATABASE_URL` como origem; `alembic upgrade head` aplica as 4 migrações e o offline SQL usa dialeto PostgreSQL.
- Guarda de `SECRET_KEY` validada: chave dev de 21 bytes → `RuntimeError`; chave de 32+ bytes → inicializa.
- Segredos: `.env` ignorado pelo Git; apenas `.env.example` versionado (placeholders); nenhuma credencial rastreada.

**DIVERGÊNCIAS NO `.env` LOCAL (corrigir na VPS, não é código):**
- Usuário do banco `industrial_app` (não-superuser) é o usuário real da aplicação; a
  documentação antiga mencionava `industrial_erp`, que no PG real ainda é SUPERUSER
  (corrigido na TASK-024 — ver nota abaixo).
- `SECRET_KEY=GERE_UMA_CHAVE_SEGURA` (21 bytes) não passa na validação mínima de 32 bytes.

**NÃO VALIDÁVEL NESTE AMBIENTE:**
- `alembic upgrade head`/`pg_isready`/teste TCP contra o PostgreSQL 16 real (sem Docker daemon nem servidor PostgreSQL local) — permanece pendente na VPS (TASK-021).

**ARQUIVOS ALTERADOS:**
- `TASKS.md` — TASK-023 registrada com a infra real e os resultados de validação.

**TESTES:**
```
257 passed (venv Python 3.11)
```

**SECURITY AUDIT:**
- Porta 5432 somente loopback; 8000 somente loopback via `network_mode: host`.
- Autenticação SCRAM; role sem privilégios administrativos.
- Secrets somente via ambiente; nada no Git.

**PRÓXIMA TAREFA:**
TASK-021 — executar `alembic upgrade head` e smoke test PP-PI→QM→CO contra o PostgreSQL real na VPS.

---

## TASK-022 — Revisão da configuração de produção (PostgreSQL externo)

**Status:** DONE

**Data:** 2026-08-15

**IMPLEMENTADO:**
- `docker-compose.prod.yml` — removido serviço `db` e volume `pgdata`; API com `network_mode: host` alcançando `127.0.0.1:5432`; uvicorn bind `127.0.0.1:8000`; `DATABASE_URL` e `SECRET_KEY` obrigatórios via env.
- `.env.example` — placeholders: `DATABASE_URL=postgresql://industrial_erp:<password>@127.0.0.1:5432/industrial_erp`, `SECRET_KEY=` vazio.
- `deploy/nginx.conf.example` — `proxy_pass http://127.0.0.1:8000`.
- `README.md` e `docs/RUNBOOK.md` — seção de deploy com PostgreSQL externo + host networking.

**ARQUIVOS ALTERADOS:**
- `docker-compose.prod.yml`, `.env.example`, `deploy/nginx.conf.example`, `README.md`, `docs/RUNBOOK.md`, `TASKS.md`

**VALIDAÇÃO (2026-08-15):**
- `docker compose -f docker-compose.prod.yml config --quiet` (compose v2) → OK
- `pytest` → 257 passed · `npm run typecheck` → OK
- `python -m compileall app/ database/` → OK

**SECURITY AUDIT:**
- Sem credenciais hardcoded; secrets via ambiente.
- API não exposta publicamente (loopback + reverse proxy).

**PRÓXIMA TAREFA:**
TASK-023 registrada; TASK-021 (validação operacional em staging) pendente.

---

## TASK-021 — Validação final para deploy em produção (validação de integração executada)

**Status:** IN PROGRESS

**Data:** 2026-08-15

**IMPLEMENTADO (validação de integração das configurações):**
- PostgreSQL externo provisionado na VPS (TASK-023): container, volume, banco/usuário/schema, role sem superuser, `pg_hba.conf` scram-sha-256, porta 5432 somente loopback.
- Engine PostgreSQL/psycopg2 com pool config validado; Alembic via `DATABASE_URL`; guarda de `SECRET_KEY` (32+ bytes) validada.
- Segredos fora do Git confirmados (`.env` ignorado, `.env.example` apenas placeholders).

**PENDENTE (depende da VPS):**
- `alembic upgrade head` contra o PostgreSQL real.
- Smoke test PP-PI → QM → CO em PostgreSQL real.
- `TRUSTED_PROXY_IPS` real, TLS/HTTPS, confirmação de firewall.
- Backup, restauração e rollback detalhados.

**TESTES:**
```
257 passed · typecheck OK · compose prod OK · compileall OK
```

**PRÓXIMA TAREFA:**
Executar validação operacional em staging antes do deploy público.

---

## TASK-014 — Documentação `docs/` + LICENSE

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- `docs/ARCHITECTURE.md` — camadas, integração via eventos, state machines, segurança
- `docs/BUSINESS_PROCESS.md` — fluxo PP-PI→QM→CO, cenários normal/crise, roles
- `docs/DATA_MODEL.md` — entidades, relacionamentos, constraints, enums
- `docs/SAP_MAPPING.md` — mapeamento conceitual para SAP S/4HANA (disclaimer)
- `docs/RUNBOOK.md` — local/Docker/produção, setup do domínio `erp.francorafael.com` (Cloudflare), manutenção, checklist de segurança
- `LICENSE` (MIT)
- `README.md` — link para `docs/`

**ARQUIVOS CRIADOS:**
- `docs/{ARCHITECTURE,BUSINESS_PROCESS,DATA_MODEL,SAP_MAPPING,RUNBOOK}.md`, `LICENSE`

**ANÁLISE DE DOMÍNIO (erp.francorafael.com):**
- Viável: `francorafael.com` já está na Cloudflare; o subdomínio `erp` usa Universal SSL (wildcard) automaticamente.
- DNS: registro `erp` (CNAME → `francorafael.com` ou `A` → IP da VPS), proxy laranja.
- Alternativa sem portas abertas: Cloudflare Tunnel roteando `erp.francorafael.com` → `http://localhost:8000`.

**TESTES:**
```
248 passed (sem mudança de código Python)
```

**PRÓXIMA TAREFA:**
Nenhuma — sequência concluída. Pendências: automação externa (opcional), I-84/I-86 (decisões de infra).

---

## TASK-019.1/TASK-020.1 — Correções Pós-Auditoria (L-43, I-82, I-83, I-85)

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- **L-43:** `deploy/nginx.conf` → `deploy/nginx.conf.example` (template explícito) + comentário de substituição do `<DOMAIN>`
- **I-82:** `healthcheck` no `docker-compose.prod.yml` (urllib → `/health`, valida API + DB)
- **I-83:** comentário documentando que TLS é terminado no Cloudflare/Nginx Proxy Manager
- **I-85:** `cache: "pip"` no `actions/setup-python` do CI

**ARQUIVOS ALTERADOS:**
- `deploy/nginx.conf.example` (renomeado de nginx.conf)
- `docker-compose.prod.yml`, `.github/workflows/ci.yml`, `README.md`

**TESTES:**
```
248 passed in 20.70s
```
- `pytest` OK · `typecheck` OK · `lint` OK · YAML validados

**ADIADOS (decisão — próxima etapa):**
- I-84: pinar hadolint-action a commit SHA
- I-86: imagem base alpine vs slim

**PRÓXIMA TAREFA:**
Nenhuma — sequência concluída. Pendências: docs/ + LICENSE (registrada), automação externa (opcional), I-84/I-86 (decisão).

---

## TASK-020 — CI/hardening (multi-stage build, hadolint, docker compose config)

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- `Dockerfile` — multi-stage build (estágio builder com venv → runtime não-root `appuser`)
- `.github/workflows/ci.yml` — jobs: `test` (pytest + compileall) e `docker` (hadolint + `docker compose config`)
- `.dockerignore` — exclui `.github`, `deploy`, `docker-compose*.yml` (arquivos host-side)

**ARQUIVOS ALTERADOS:**
- `Dockerfile`, `.dockerignore`
- `.github/workflows/ci.yml` (criado)

**TESTES:**
```
248 passed in 21.31s
```
- `pytest` OK · `typecheck` OK · `lint` OK
- YAML do `ci.yml` e compose files validados

**SECURITY AUDIT:**
- Container não-root mantido no multi-stage (I-38/L-38)
- CI valida Dockerfile (hadolint) e compose files (I-66/I-67)
- Sem secrets no workflow

**PRÓXIMA TAREFA:**
Nenhuma — sequência concluída. Pendências: docs/ + LICENSE (registrada), automação externa (opcional).

---

## TASK-019 — Infraestrutura real (deploy VPS/Cloudflare/PostgreSQL central)

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- `docker-compose.prod.yml` — produção sem `db` local (reusa PostgreSQL central via `DATABASE_URL`), `TRUST_PROXY_HEADERS=true`
- `deploy/nginx.conf` — exemplo de reverse proxy (`X-Forwarded-For`)
- `README.md` — seção "Deployment (Production)" (compose prod, reverse proxy, Cloudflare, bootstrap)

**ARQUIVOS CRIADOS:**
- `docker-compose.prod.yml`, `deploy/nginx.conf`

**ARQUIVOS ALTERADOS:**
- `README.md`

**DOCUMENTOS CONSULTADOS:**
- `plano/02-arquitetura-infraestrutura.md` — VPS, Docker, Cloudflare, PostgreSQL central

**TESTES:**
```
248 passed in 20.82s
```
- `pytest` OK · `typecheck` OK · `lint` OK · YAML compose prod validado

**SECURITY AUDIT:**
- `SECRET_KEY`/`DATABASE_URL` obrigatórios via env (sem fallback)
- `TRUST_PROXY_HEADERS=true` atrás de reverse proxy
- Sem credenciais hardcoded

**PRÓXIMA TAREFA:**
TASK-020 — CI/hardening

---

## TASK-018 — Integração PP→QM→CO passo 6 (rework cost automático)

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- `EVENT_INSPECTION_FAILED = "inspection.failed"` no `app/core/events.py`
- `QualityService.update_inspection_result(FAILED)` publica o evento antes do commit (com `try/except Exception: rollback()`)
- `app/services/integration.py`:
  - `_on_inspection_failed` — encontra batch→ordem→cost record e aplica rework
  - `_apply_rework_to_order` — aplica +8% (`_REWORK_COST_FACTOR`) aos custos reais (idempotente: no-op se `actual_total_cost` já setado)
  - `_auto_create_cost_record` (order.completed) — se já houve inspeção FAILED, aplica rework ao criar o cost record
- Cobre ambos os fluxos: inspeção falha antes OU depois da ordem completar

**ARQUIVOS ALTERADOS:**
- `app/core/events.py` — `EVENT_INSPECTION_FAILED`
- `app/services/integration.py` — handler rework + verificação no order.completed
- `app/services/quality_service.py` — publish do evento + rollback
- `tests/unit/test_integration.py` — 2 testes novos (`TestReworkIntegration`)

**DOCUMENTOS CONSULTADOS:**
- `plano/08-integracao-eventos.md` — passo 6: "Se QM = FAIL → CO registra impacto financeiro do retrabalho/scrap"

**TESTES:**
```
248 passed in 20.74s
```
- `.venv/bin/pytest tests/` → **248 passed** (era 246)
- `npm run typecheck` → OK
- `npm run lint` → OK
- Smoke test: planned R$ 24.300 → actual R$ 26.244 (rework +8%, variance R$ 1.944)

**AUTO REVIEW:**
- Passo 6 do plano/08 agora implementado (QM→CO)
- Idempotente (rework aplicado uma vez por ordem)
- Cobre ambos os fluxos (falha antes/depois da ordem completar)

**SECURITY AUDIT:**
- SQL injection: ✅ ORM parametrizado
- Integridade transacional: ✅ evento publicado antes do commit + rollback
- Idempotência: ✅ `actual_total_cost is not None` impede duplicação
- Sem input de usuário

**PRÓXIMA TAREFA:**
TASK-019 — Infraestrutura real (deploy VPS/Cloudflare/PostgreSQL central)

---

## TASK-017 — Telas por módulo (Production, Quality, Cost)

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- `templates/dashboard/production.html` — KPIs (volume, OEE, machine utilization, completion) + contagens (materials/recipes/resources) + tabela de recent orders
- `templates/dashboard/quality.html` — KPIs (pass/failure rate, NCs, pending) + tabela de recent inspections
- `templates/dashboard/costing.html` — KPIs (planned/actual, variance, cost/liter, quality cost) + tabela cost by material
- Rotas `/dashboard/production`, `/dashboard/quality`, `/dashboard/costing`
- `base.html` — navegação com `active_nav` dinâmico (home/production/quality/cost/order-360) + CSS de tabelas

**ARQUIVOS CRIADOS:**
- `templates/dashboard/production.html`, `quality.html`, `costing.html`

**ARQUIVOS ALTERADOS:**
- `app/api/dashboard.py` — 3 rotas + `active_nav` no contexto de todas as páginas
- `templates/dashboard/base.html` — navegação + CSS
- `tests/unit/test_dashboard.py` — 3 testes novos

**DOCUMENTOS CONSULTADOS:**
- `plano/09-dashboard.md` — telas por módulo (Production/Quality/Cost)

**TESTES:**
```
246 passed in 20.54s
```
- `.venv/bin/pytest tests/` → **246 passed** (era 243)
- `npm run typecheck` → OK
- `npm run lint` → OK
- Smoke test: todas as 5 páginas renderizam 200 com dados simulados

**AUTO REVIEW:**
- Reusa os dados já existentes do `AnalyticsService` (executive_kpis + stats)
- Navegação consistente com `active_nav` dinâmico
- Estilo consistente com o `home.html` (kpi-card/table-card)

**SECURITY AUDIT:**
- XSS: ✅ Jinja2 escapa por padrão; sem `tojson` de dados não-sanitizados
- Rotas HTML públicas (I-31, documentado) — endpoints de dados protegidos por RBAC
- Sem input de usuário

**PRÓXIMA TAREFA:**
TASK-018 — Integração PP→QM→CO passo 6 (rework cost automático)

---

## TASK-016.1 — Correções Pós-Auditoria (L-42, I-69, I-72)

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- **L-42:** `oee = min(1.0, availability * performance * quality)` — clamp em 100%
- **I-69:** `create_confirmation`/`create_consumption` com `try/except Exception: rollback(); raise`
- **I-72:** testes `test_oee_expected_values` (96%) e `test_oee_clamped_at_100`

**ARQUIVOS ALTERADOS:**
- `app/analytics/service.py`, `app/services/production_service.py`
- `tests/unit/test_dashboard.py` — helper `_create_oee_scenario` + 2 testes

**TESTES:**
```
243 passed in 21.24s
```
- `compileall` OK · `typecheck` OK · `lint` OK

**SECURITY AUDIT:**
- 0 CRITICAL/HIGH/MEDIUM/LOW restantes
- Pendência INFO (I-71 otimização OEE): documentada como "ação futura"

**PRÓXIMA TAREFA:**
TASK-017 — Telas por módulo (Production, Quality, Cost)

---

## TASK-016 — Indicadores avançados (OEE, Machine Utilization, Cost per Liter, Quality Cost)

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- `AnalyticsService.oee()` — `availability` (razão planned/actual duration das ordens completadas) × `performance` (yield) × `quality` (pass rate)
- `AnalyticsService.machine_utilization()` — % de recursos que produziram ao menos 1 batch
- `AnalyticsService.cost_per_liter()` — custo real (fallback planejado) por litro produzido
- `AnalyticsService.quality_cost()` — variância de custo das ordens com inspeção FAILED (rework/scrap)
- Integrados ao `executive_kpis()` como chaves top-level (`oee`, `machine_utilization`, `cost_per_liter`, `quality_cost`)
- 4 novos KPI cards no `home.html` (OEE, Machine Utilization, Cost per Liter, Quality Cost)

**ARQUIVOS ALTERADOS:**
- `app/analytics/service.py` — 4 métodos + integração no `executive_kpis`
- `templates/dashboard/home.html` — 4 KPI cards
- `tests/unit/test_dashboard.py` — 5 testes novos

**DOCUMENTOS CONSULTADOS:**
- `plano/05-dominio-pp-pi.md` — OEE, utilização de máquina
- `plano/09-dashboard.md` — OEE, Cost per Liter, Quality Cost, Machine Utilization

**TESTES:**
```
241 passed in 20.60s
```
- `.venv/bin/pytest tests/` → **241 passed** (era 236)
- `npm run typecheck` → OK
- `npm run lint` → OK
- Smoke test: OEE 84.2% (A 98.2% × P 92.8% × Q 92.4%), Machine Utilization 100%, Cost/Liter R$ 2.86, Quality Cost R$ 14k

**AUTO REVIEW:**
- OEE deriva availability dos dados reais de duração (planned vs actual), performance do yield e quality do pass rate — sem valores hardcoded
- Indicadores são read-only (SELECT), sem transação
- Integração consistente com o padrão do `executive_kpis`

**SECURITY AUDIT:**
- SQL injection: ✅ ORM parametrizado
- Divisão por zero tratada em todos os cálculos
- Sem input de usuário; endpoints read-only

**PRÓXIMA TAREFA:**
TASK-017 — Telas por módulo (Production, Quality, Cost)

---

## TASK-015 — API ProductionConfirmation + MaterialConsumption

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- Schema `MaterialConsumptionBase/Create/MaterialConsumption` adicionado a `app/domain/production/batch.py` (junto a `ProductionConfirmation`)
- `ProductionConfirmationRepository` + `MaterialConsumptionRepository` em `app/repositories/production_repository.py` (get_by_batch + count_by_batch)
- `ProductionService.create_confirmation` / `list_confirmations_by_batch` e `create_consumption` / `list_consumptions_by_batch`
- `create_consumption` valida unit vs `material.base_unit` (reusa `ComponentUnitMismatchError` → 422)
- 4 endpoints no router PP-PI:
  - `POST /api/production/confirmations`, `GET /api/production/batches/{batch_id}/confirmations`
  - `POST /api/production/consumptions`, `GET /api/production/batches/{batch_id}/consumptions`
- `tests/unit/test_api_confirmations.py` — 8 testes (CRUD, 404 batch/material, 422 unit mismatch)

**ARQUIVOS ALTERADOS:**
- `app/domain/production/batch.py`, `app/repositories/production_repository.py`, `app/services/production_service.py`, `app/api/production.py`
- `tests/unit/test_api_confirmations.py` (criado)

**DOCUMENTOS CONSULTADOS:**
- `plano/05-dominio-pp-pi.md` — Production Confirmation, Material Consumption
- `plano/04-arquitetura-software.md` — routers/endpoints

**TESTES:**
```
236 passed in 20.25s
```
- `.venv/bin/pytest tests/` → **236 passed** (era 228)
- `npm run typecheck` → OK
- `npm run lint` → OK

**AUTO REVIEW:**
- Segue o padrão das tarefas anteriores (repository + service + thin API + paginação)
- Validação de unidade consistente com RecipeComponent (M-11/L-05)

**SECURITY AUDIT:**
- SQL injection: ✅ ORM parametrizado
- Input: ✅ Pydantic (gt=0, decimal_places, max_length)
- RBAC: ✅ router protegido por `require_api_access`
- Erros: ✅ 404 (batch/material), 422 (unit mismatch)

**PRÓXIMA TAREFA:**
TASK-016 — Indicadores avançados (OEE, Machine Utilization, Cost per Liter, Quality Cost)

---

## TASK-013.1 — Correções Pós-Auditoria (M-23, L-38, L-39, L-40, I-64, I-65, I-68)

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- **M-23:** credenciais do `db` movidas para env vars (`${POSTGRES_USER/PASSWORD/DB}`), adicionadas ao `.env.example`
- **L-38:** `useradd appuser` + `USER appuser` + `COPY --chown` no Dockerfile
- **L-39:** removido `ports` do serviço `db` (sem exposição ao host)
- **L-40:** `SECRET_KEY: ${SECRET_KEY}` obrigatório (sem fallback)
- **I-64:** `mem_limit: 512m` no serviço `api`
- **I-65/I-68:** seção "Environment Variables" + nota de produção (rate limiting, TRUST_PROXY_HEADERS) no README

**ARQUIVOS ALTERADOS:**
- `Dockerfile`, `docker-compose.yml`, `.env.example`, `README.md`

**TESTES:**
```
228 passed in 19.92s
```
- `pytest` OK · `typecheck` OK · `lint` OK · YAML do compose validado

**SECURITY AUDIT:**
- 0 CRITICAL/HIGH/MEDIUM/LOW restantes
- Pendências INFO (I-63 multi-stage, I-66/I-67 CI): documentadas como "ação futura"

**PRÓXIMA TAREFA:**
TASK-014 — Documentação `docs/` (ARCHITECTURE, BUSINESS_PROCESS, DATA_MODEL, SAP_MAPPING, RUNBOOK)

---

## TASK-013 — Docker/deploy

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- `Dockerfile` — `python:3.11-slim`, instala `requirements.txt`, `uvicorn app.main:app` na porta 8000
- `docker-compose.yml` — `db` (PostgreSQL 16-alpine, healthcheck `pg_isready`, volume persistente) + `api` (build, `depends_on` com `service_healthy`, `alembic upgrade head && uvicorn`)
- `.dockerignore` — exclui `.venv`, `node_modules`, legado Vite/React (`src/`, `public/`, `dist/`, `package*.json`, `tsconfig*`, `vite.config.ts`), docs, tests, `.env`
- `README.md` — reescrito: overview dos módulos PP-PI/QM/CO, disclaimer sintético/"inspired by SAP", features, stack, Docker/local quick start, uso (auth/RBAC/API/dashboard/simulação), testes, estrutura, docs

**ARQUIVOS CRIADOS:**
- `Dockerfile`, `docker-compose.yml`, `.dockerignore`
- `README.md` (substituiu o README legado do template Vite)

**DOCUMENTOS CONSULTADOS:**
- `plano/02-arquitetura-infraestrutura.md` — Docker, PostgreSQL central, Cloudflare
- `plano/12-estrutura-repositorio.md` — Dockerfile/compose/README na raiz

**TESTES:**
```
228 passed in 19.94s
```
- `.venv/bin/pytest tests/` → **228 passed** (sem mudança de código Python)
- `npm run typecheck` → OK
- `npm run lint` → OK
- YAML do `docker-compose.yml` validado (parse `yaml.safe_load`)

**AUTO REVIEW:**
- `python:3.11-slim` compatível com `psycopg2-binary` (glibc)
- Compose segue `plano/02`: DB local só para dev; produção reusa PostgreSQL central via `DATABASE_URL`
- Seed (admin + dados) manual via `docker compose exec` — sem senha default hardcoded
- `.dockerignore` mantém a imagem enxuta (sem legado React/tests/docs)

**SECURITY AUDIT:**
- Credenciais do DB local (`erp:erp`) são para desenvolvimento — documentado; produção usa PostgreSQL central com credenciais via env
- `SECRET_KEY` via env com fallback placeholder (documentado)
- `.env` excluído da imagem (`.dockerignore`)
- Senha do admin nunca hardcoded no compose (seed manual)

**PENDÊNCIAS:**
- `docs/` (ARCHITECTURE, BUSINESS_PROCESS, DATA_MODEL, SAP_MAPPING, RUNBOOK) — TASK-014
- `.env.example` com `DATABASE_URL` apontando para localhost (dev)

**PRÓXIMA TAREFA:**
TASK-014 — Documentação `docs/` (ARCHITECTURE, BUSINESS_PROCESS, DATA_MODEL, SAP_MAPPING, RUNBOOK)

---

## TASK-012.1 — Correções Pós-Auditoria (M-22, L-35, L-36, L-37, I-56, I-62)

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- **M-22:** `create_batch` e `update_order_status` fazem `except Exception: rollback(); raise` após publicar eventos
- **L-35:** teste de idempotência `test_cost_record_not_duplicated`
- **L-36:** documentação reforçada (placeholder per-liter, não derivado do BOM)
- **L-37:** `order.completed` publicado também para `PARTIAL`
- **I-56/I-62:** `EventBus.unsubscribe()` + teste `test_create_batch_rolls_back_when_handler_fails`

**ARQUIVOS ALTERADOS:**
- `app/core/events.py` — `unsubscribe()`
- `app/services/production_service.py` — rollback genérico + evento para PARTIAL
- `app/services/integration.py` — docstring
- `tests/unit/test_integration.py` — +2 testes

**TESTES:**
```
228 passed in 19.79s
```
- `compileall` OK · `typecheck` OK · `lint` OK · `alembic upgrade/downgrade` OK

**SECURITY AUDIT:**
- 0 CRITICAL/HIGH/MEDIUM/LOW restantes
- Pendências INFO (I-57, I-58, I-61): documentadas como "ação futura"

**PRÓXIMA TAREFA:**
TASK-013 — Docker/deploy (Dockerfile + docker-compose + README)

---

## TASK-012 — Integração automática PP→QM→CO via eventos

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- `app/core/events.py` — `EventBus` in-memory (subscribe/publish) + `EVENT_BATCH_CREATED` / `EVENT_ORDER_COMPLETED`
- `app/services/integration.py` — handlers idempotentes registrados via `register_integration_handlers()` (chamado no `main.py`):
  - `batch.created` → auto-cria `QualityInspection` PENDING (gatilho QM, conforme `plano/06`)
  - `order.completed` → auto-cria `CostRecord` com custos planejados estimados por litro (gatilho CO)
- `ProductionService.create_batch` publica `batch.created` antes do commit
- `ProductionService.update_order_status(COMPLETED)` publica `order.completed` antes do commit
- Contrato transacional: handlers usam repositórios (flush), o publisher commita — tudo numa única transação
- Handlers verificam se o registro já existe (idempotentes, sem duplicação)

**ARQUIVOS CRIADOS:**
- `app/core/events.py`
- `app/services/integration.py`
- `tests/unit/test_integration.py` (4 testes)

**ARQUIVOS ALTERADOS:**
- `app/services/production_service.py` — importa `event_bus` + publica eventos
- `app/main.py` — `register_integration_handlers()` no startup
- `tests/conftest.py` — autouse fixture registra handlers
- `tests/unit/test_api_quality.py` — testes atualizados para o fluxo automático (batch já cria inspeção PENDING)

**DOCUMENTOS CONSULTADOS:**
- `plano/08-integracao-eventos.md` — modelo de eventos PP-PI→QM→CO
- `plano/06-dominio-qm.md` — gatilho "toda ordem gera inspeção vinculada ao batch"

**TESTES:**
```
226 passed in 20.02s
```
- `.venv/bin/python -m compileall app/` → OK
- `.venv/bin/pytest tests/` → **226 passed** (era 222)
- `npm run typecheck` → OK
- `npm run lint` → OK
- Smoke test API: criar batch → auto-inspeção PENDING; completar ordem → auto cost record (planned_total R$ 24.300)

**AUTO REVIEW:**
- EventBus desacopla módulos (PP-PI não importa QM/CO diretamente)
- Handlers idempotentes + repositórios flush-only preservam atomicidade (M-05)
- Simulação usa ORM direto (não dispara eventos) — correto, pois gera inspeções/custos próprios
- Testes de qualidade refletem o novo fluxo automático

**SECURITY AUDIT:**
- SQL injection: ✅ ORM parametrizado; sem input de usuário nos handlers
- inspection_lot auto: derivado de `batch.id` (autoincrement), sem input externo
- custos auto: calculados da quantidade da ordem, sem input externo
- EventBus: in-memory síncrono, sem rede/serialização (sem superfície de ataque)
- Secrets: ✅ Nenhum

**PENDÊNCIAS:**
- Passo 6 do plano/08 (impacto QM→CO de rework quando inspeção FAIL) não implementado automaticamente — o cost record é criado no completion; o fator de rework é demonstrado na simulação
- Atomicidade "eventual" entre módulos se o publisher não commit (o `session_dependency` faz rollback automático)

**PRÓXIMA TAREFA:**
TASK-013 — Docker/deploy (Dockerfile + docker-compose + README)

---

## TASK-011.1 — Correções Pós-Auditoria (L-33, L-34, I-51, I-54)

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- **L-33:** fallback explícito `actual_quantity if is not None else planned_quantity` (Decimal "0" não é mais tratado como falsy)
- **L-34:** `.where(ProductionOrder.planned_start.isnot(None))` na query de ordens
- **I-51:** loops de volume/custo e qualidade consolidados em um único loop
- **I-54:** 3 testes de borda adicionados

**ARQUIVOS ALTERADOS:**
- `app/analytics/service.py` — `monthly_trend` corrigido
- `tests/unit/test_dashboard.py` — helper `_create_order` + 3 testes

**TESTES:**
```
222 passed in 20.27s
```
- `compileall` OK · `typecheck` OK · `lint` OK · `alembic upgrade/downgrade` OK

**SECURITY AUDIT:**
- 0 CRITICAL/HIGH/MEDIUM/LOW restantes
- Pendências INFO (I-50, I-52, I-53, I-55): documentadas como "ação futura"

**PRÓXIMA TAREFA:**
TASK-012 — Integração automática PP→QM→CO via eventos

---

## TASK-011 — Dashboard consumindo dados simulados + KPIs de tendência

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- `AnalyticsService.monthly_trend()` — agregação mensal de PP-PI/QM/CO (orders, volume_litros, pass_rate, planned/actual cost), ordenada por mês (`YYYY-MM`)
- `GET /api/dashboard/monthly-trend` — endpoint de dados (protegido via `require_api_access` no router)
- `templates/dashboard/home.html` — 2 novos gráficos de tendência:
  - Volume (bar) + Pass Rate (line, eixo secundário) por mês
  - Cost Planned vs Actual (lines) por mês
- `dashboard_home` passa `monthly_trend` ao contexto do template
- Agregação em Python (portável SQLite/PostgreSQL) com 3 queries simples; adequada ao volume simulado

**ARQUIVOS ALTERADOS:**
- `app/analytics/service.py` — `monthly_trend()` + import `defaultdict`
- `app/api/dashboard.py` — endpoint `/monthly-trend` + contexto
- `templates/dashboard/home.html` — gráficos de tendência
- `tests/unit/test_dashboard.py` — 3 testes novos

**DOCUMENTOS CONSULTADOS:**
- `plano/09-dashboard.md` — KPIs e telas
- `plano/10-simulacao.md` — cenário de crise (causa e efeito)
- `plano/08-integracao-eventos.md` — fluxo PP-PI→QM→CO

**TESTES:**
```
219 passed in 20.00s
```
- `.venv/bin/python -m compileall app/` → OK
- `.venv/bin/pytest tests/` → **219 passed** (era 216)
- `npm run typecheck` → OK
- `npm run lint` → OK
- `alembic upgrade/downgrade` → OK
- Smoke test: 3 meses crise → pass_rate 95.7% → 95.5% → 85.7%; custo subindo (demonstra tendência)

**AUTO REVIEW:**
- `monthly_trend()` simples e portável (agregação em Python, sem SQL específico de engine)
- Endpoint protegido pelo RBAC existente (GET → viewer+)
- Template usa `tojson` (XSS-safe) e Plotly; dados dinâmicos via server-side render

**SECURITY AUDIT:**
- SQL injection: ✅ ORM parametrizado, sem input de usuário
- XSS: ✅ `tojson` escapa os dados no template
- Secrets: ✅ Nenhum
- Validação: ✅ Sem parâmetros de entrada (endpoint read-only)

**PENDÊNCIAS:**
- Dashboard HTML (`/dashboard/`) permanece público (I-31) — login UI futura
- Tendência agrega em Python; para >100k ordens, migrar para SQL `GROUP BY` com `extract`

**PRÓXIMA TAREFA:**
TASK-012 — Integração automática PP→QM→CO via eventos (auto-trigger de inspeção + cost record)

---

## TASK-010.1 — Correções Pós-Auditoria (L-27..L-32, I-42..I-45)

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- **L-27:** `reset_database` exige `--yes` ou prompt interativo; lógica em `reset_domain_data()` testável
- **L-28:** `SimulationConfig.from_env` usa `_parse()` com `try/except ValueError` (mensagem clara)
- **L-29:** `yield_std` (código morto) removido de `SimulationConfig`
- **L-30:** engine commita master data logo após `generate_master_data` (corrige `months=0`)
- **L-31:** `_clamp()` em pH/alcohol/temperature/co2 antes de `to_decimal`
- **L-32:** `_planned_material_cost` derivado do BOM (component.quantity × preço unitário) — PP-PI↔CO reconciliado
- **I-42:** `ctx.recipe_by_id` (O(1)) substitui busca linear
- **I-43:** `to_decimal` rejeita valor não-finito
- **I-44:** `add_months` clampa o dia com `calendar.monthrange`
- **I-45:** `logger.info` mensal no loop do engine

**ARQUIVOS ALTERADOS:**
- `app/simulation/config.py`, `production_generator.py`, `quality_generator.py`, `cost_generator.py`, `engine.py`
- `scripts/reset_database.py`
- `tests/unit/test_simulation.py` (+4 testes)

**TESTES:**
```
216 passed in 20.14s
```
- `compileall` OK · `typecheck` OK · `lint` OK · `alembic upgrade/downgrade` OK
- Smoke test: `reset_database` sem `--yes` aborta; com `--yes` limpa preservando `users`

**AUTO REVIEW:**
- Correções minimamente invasivas; custo de material agora coerente com o BOM
- `reset_domain_data` extraído para testabilidade

**SECURITY AUDIT:**
- 0 CRITICAL/HIGH/MEDIUM/LOW restantes após correções
- Pendências INFO (I-46..I-49): documentadas como "ação futura"

**PRÓXIMA TAREFA:**
TASK-011 — Dashboard consumindo dados simulados + KPIs de tendência

---

## TASK-010 — Simulation Engine + Seed de Dados Sintéticos

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- `app/simulation/config.py` — `SimulationConfig` (from_env + CLI), `MonthParams`, `SimulationSummary`, `SimulationContext`, helpers `to_decimal`/`add_months`
- `app/simulation/production_generator.py` — master data (3 finished products, 5 raw, 3 packaging, 3 recipes com BOM+roteiro, 5 resources) + ordens + batches + confirmações + consumos
- `app/simulation/quality_generator.py` — inspeções (PASSED/FAILED) + não-conformidades em falha
- `app/simulation/cost_generator.py` — CostRecord planned/actual (variância + fator de retrabalho em falha QM)
- `app/simulation/engine.py` — `SimulationEngine` orquestrando PP-PI → QM → CO; cenário "crisis" (downtime → yield → qualidade → rework → custo)
- `scripts/generate_data.py` — CLI `--months --seed --scenario --orders-per-month`
- `scripts/reset_database.py` — reseta tabelas de domínio (preserva `users`)
- Integração PP→QM→CO: falha de qualidade (QM FAIL) → fator de custo de retrabalho (CO)

**BUG CORRIGIDO (infra compartilhada):**
- `CostRecord` CHECK constraints trocadas de igualdade exata para tolerância (`ABS(...) < 0.01`): a igualdade exata falha no SQLite para valores Decimal não-arredondados (NUMERIC → REAL float). PostgreSQL (NUMERIC exato) permanece correto. Migração `b2c3d4e5f6a7`.

**ARQUIVOS CRIADOS:**
- `app/simulation/{config,production_generator,quality_generator,cost_generator,engine}.py`
- `scripts/generate_data.py`, `scripts/reset_database.py`
- `database/migrations/versions/b2c3d4e5f6a7_cost_check_tolerance.py`
- `tests/unit/test_simulation.py` (9 testes)

**ARQUIVOS ALTERADOS:**
- `app/simulation/__init__.py` — exports
- `app/domain/entities.py` — CHECK constraints `CostRecord` com tolerância

**DOCUMENTOS CONSULTADOS:**
- `plano/10-simulacao.md` — parâmetros, cenários, scripts
- `plano/04-arquitetura-software.md` — estrutura `app/simulation/`
- `plano/08-integracao-eventos.md` — fluxo PP-PI→QM→CO
- `plano/01-visao-geral.md` — módulos e disclaimer sintético

**TESTES:**
```
212 passed in 19.66s
```
- `.venv/bin/python -m compileall app/ scripts/` → OK
- `.venv/bin/pytest tests/` → **212 passed** (era 203)
- `npm run typecheck` → OK
- `npm run lint` → OK
- `alembic upgrade/downgrade` → OK (migração `b2c3d4e5f6a7` aplicada/revertida)
- Smoke test CLI: `--months 3` → 30 ordens, 65 batches, 65 inspeções, 996 registros; `--months 12 --scenario crisis` → 180 ordens, 378 batches, 5708 registros

**AUTO REVIEW:**
- Engine isolado em `app/simulation/` (sem acoplamento com `app/api/`/`app/main.py`)
- Geradores separados por módulo (PP-PI/QM/CO) conforme plano; contexto compartilhado via `SimulationContext`
- Decimal para dinheiro e quantidades; dados sintéticos documentados em docstrings
- Determinístico com `seed` (testado)
- Estado final é setado diretamente (COMPLETED/PASSED/FAILED) — correto para geração de histórico, sem passar pela máquina de estados do service
- Ordem de dependências respeitada (flush antes de consumir IDs de batch/inspection)

**SECURITY AUDIT:**
- SQL injection: ✅ ORM/table-level, sem input de usuário
- Secrets: ✅ Nenhum; dados sintéticos documentados
- Input: ✅ CLI args tipados (`choices` para scenario)
- Exposição: ✅ Scripts são CLI (não endpoints); sem credenciais
- Destrutivo: `reset_database` é CLI explícito, preserva `users`

**PENDÊNCIAS:**
- Volumes default (180 ordens, ~378 inspeções, ~5.7k registros) abaixo do alvo ilustrativo do plano (~540 inspeções, ~50k registros) — configurável via `--orders-per-month`/`--months`
- `create_all` nos scripts de seed (bootstrap) em vez de Alembic — documentado
- Seed não executa automaticamente no startup da aplicação (TASK futura se desejado)

**PRÓXIMA TAREFA:**
TASK-011 — Dashboard consumindo dados simulados + KPIs de tendência (ou seed automático + documentação de deploy)

---

## TASK-009.1 — Correções Pós-Auditoria (M-20, M-21, L-22..L-26, I-29, I-32..I-34)

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- **M-20:** `_client_key()` lê `X-Forwarded-For`/`X-Real-IP` quando `TRUST_PROXY_HEADERS=true` (env var); fallback para `client.host`
- **M-21:** `_cleanup()` no rate limiter remove chaves expiradas a cada 60s (elimina memory leak)
- **L-22:** login constant-time — `authenticate` sempre roda `verify_password` com hash dummy (`_DUMMY_PASSWORD_HASH`)
- **L-23:** `_resolve_role()` em `dependencies.py` — role inválido → 403 (não 500)
- **L-24:** `verify_password` rejeita hash com `iterations < _MIN_ITERATIONS` (600k)
- **L-25:** `PARTIAL → {COMPLETED}` adicionado ao state machine
- **L-26:** cascade `Batch.production_confirmations` e `Batch.material_consumptions` (`delete-orphan`)
- **I-29:** warning de log quando `SECRET_KEY` < 32 bytes
- **I-32:** claim `role` removido do JWT; `create_access_token(subject)`
- **I-33:** `scripts/create_user.py` usa `getpass` (senha fora do `ps`)
- **I-34:** lockout de conta — colunas `failed_attempts`/`locked_until`, 5 falhas → 15 min (HTTP 423), reset no sucesso

**ARQUIVOS CRIADOS:**
- `database/migrations/versions/a1b2c3d4e5f6_lockout.py`
- `tests/unit/test_cascade.py` (2 testes)

**ARQUIVOS ALTERADOS:**
- `app/middleware/rate_limit.py` (M-20/M-21)
- `app/services/auth_service.py` (L-22/I-34)
- `app/security/dependencies.py` (L-23), `app/security/passwords.py` (L-24), `app/security/tokens.py` (I-29/I-32)
- `app/domain/state_machine.py` (L-25), `app/domain/entities.py` (L-26/I-34)
- `app/api/auth.py` (I-32), `scripts/create_user.py` (I-33), `.env.example` (TRUST_PROXY_HEADERS)
- `tests/unit/test_auth.py` (+5), `test_rate_limit.py` (+5), `test_state_machine.py` (+1)

**TESTES:**
```
203 passed in 16.95s
```
- `.venv/bin/python -m compileall app/` → OK
- `.venv/bin/pytest tests/` → **203 passed** (era 190)
- `npm run typecheck` → OK
- `npm run lint` → OK
- `alembic upgrade/downgrade` → OK (migração `a1b2c3d4e5f6` aplicada e revertida)

**AUTO REVIEW:**
- Login constant-time: PBKDF2 sempre executado; lockout mitiga brute-force (complemento do L-22)
- `_resolve_role` garante 403 em dados corrompidos em vez de 500
- Rate limiter resolve IP real atrás de proxy + sem crescimento ilimitado
- Correções minimamente invasivas, seguindo padrões existentes

**SECURITY AUDIT:**
- 0 CRITICAL, 0 HIGH, 0 MEDIUM, 0 LOW após correções
- ⚠️ Persistente (INFO): rate limiter distribuído multi-worker (I-30) e dashboard HTML público (I-31)

**PENDÊNCIAS:**
- I-30: rate limiter distribuído multi-worker (requer Redis) — fora do escopo
- I-31: dashboard HTML público — login UI futura

**PRÓXIMA TAREFA:**
TASK-010 — Simulation Engine + Seed de Dados Sintéticos

---

## TASK-009 — Autenticação/Autorização + Rate Limiting + Máquinas de Estado

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- **H-01 — Autenticação/Autorização (JWT + RBAC)**
  - `User` entity (`app/domain/entities.py`) com username, password_hash, role (admin/operator/viewer), is_active
  - Hashing de senha PBKDF2-HMAC-SHA256 (stdlib, sem dependência extra) em `app/security/passwords.py`
  - JWT HS256 via PyJWT em `app/security/tokens.py` (SECRET_KEY + ACCESS_TOKEN_EXPIRE_MINUTES)
  - `app/security/dependencies.py` — `get_current_user`, `require_roles`, `require_api_access` (RBAC por método HTTP: GET→viewer, POST/PUT→operator, DELETE→admin)
  - `app/api/auth.py` — `POST /api/auth/login` (OAuth2 form), `GET /api/auth/me`, `POST /api/auth/register` (admin-only)
  - Todos os routers `/api/*` (production, quality, costing, dashboard API) protegidos com `require_api_access`
  - `scripts/create_user.py` — CLI para bootstrap do primeiro admin
- **M-14/M-15 — Máquinas de Estado**
  - `app/domain/state_machine.py` — mapas de transição + `validate_transition`
  - `InvalidStateTransitionError` (→ 409) em `app/core/exceptions.py`
  - `ProductionService.update_order_status` + `PUT /api/production/orders/{id}/status`
  - `QualityService.update_inspection_result` valida transições + seta `result_date`
- **M-16 — Rate Limiting**
  - `app/middleware/rate_limit.py` — sliding-window in-memory keyed por IP, `RATE_LIMIT_PER_MINUTE`, 429
- **L-14 — Cascade Delete**
  - `ProductionOrder.batches/cost_record`, `Batch.quality_inspection`, `QualityInspection.non_conformities` com `cascade="all, delete-orphan"`

**ARQUIVOS CRIADOS:**
- `app/domain/auth.py`, `app/domain/state_machine.py`
- `app/security/__init__.py`, `passwords.py`, `tokens.py`, `dependencies.py`
- `app/repositories/user_repository.py`, `app/services/auth_service.py`, `app/api/auth.py`
- `app/middleware/__init__.py`, `app/middleware/rate_limit.py`
- `scripts/create_user.py`
- `database/migrations/versions/7b3e9c1d2a4f_users.py`
- `tests/unit/test_auth.py` (16 testes), `test_state_machine.py` (13), `test_rate_limit.py` (4)

**ARQUIVOS ALTERADOS:**
- `app/domain/entities.py` — User entity + cascades
- `app/domain/production/recipe.py` — `ProductionOrderStatusUpdate`
- `app/core/exceptions.py` — `InvalidStateTransitionError`
- `app/main.py` — auth router, middleware, handler 409
- `app/api/{production,quality,costing,dashboard}.py` — `require_api_access` + endpoint status
- `app/services/{production,quality}_service.py` — máquinas de estado
- `requirements.txt` — PyJWT + python-multipart
- `.env.example` — ACCESS_TOKEN_EXPIRE_MINUTES, RATE_LIMIT_PER_MINUTE
- `pytest.ini` — marker `no_auth`
- `tests/conftest.py` — autouse admin auth override + reset do rate limiter + SECRET_KEY de teste
- `tests/unit/test_api_quality.py` — transições estritas (PENDING→IN_PROGRESS→PASSED)

**DOCUMENTOS CONSULTADOS:**
- `plano/03-stack-tecnologica.md`, `plano/04-arquitetura-software.md`
- `plano/05-dominio-pp-pi.md`, `plano/06-dominio-qm.md`
- `auditoria.md` — H-01, M-14, M-15, M-16, L-14
- `TASKS.md` — ciclo Task → Test → Auto Review → Security Audit → Handoff

**TESTES:**
```
190 passed in 12.45s
```
- `.venv/bin/python -m compileall app/` → OK
- `.venv/bin/pytest tests/` → **190 passed** (era 158)
- `npm run typecheck` → OK
- `npm run lint` → OK
- `alembic upgrade head` + downgrade → OK (integration test)

**AUTO REVIEW:**
- Auth Python-first: JWT + RBAC sem framework externo (só PyJWT); hashing PBKDF2 stdlib
- Máquinas de estado isoladas em `domain/state_machine.py`; serviço valida antes de persistir
- Rate limiter simples, thread-safe (Lock), sem dependência; resetável para testes
- RBAC por método HTTP — política única e documentada em `require_api_access`
- Cascade delete (L-14) minimalista — só configuração de relationship, sem novo endpoint
- Testes cobrem sucesso, erro (401/403/409) e borda

**SECURITY AUDIT:**
- Secrets: `.env` não versionado; `.env.example` com placeholders; sem senha/token hardcoded
- Senhas: PBKDF2-SHA256 600k iterações + salt aleatório + `hmac.compare_digest`
- JWT: HS256 assinado; PyJWT valida exp/assinatura; `sub` usado para lookup de usuário
- SQL injection: ✅ ORM parametrizado (UserRepository)
- RBAC: viewer=read, operator=write, admin=delete (403 em insuficiência)
- Rate limiting: 429 em excesso; estado in-memory (single-instance)
- ⚠️ SECRET_KEY default (23 bytes) < 32 bytes recomendado — documentado; produção deve definir ≥32 bytes
- ⚠️ Rate limiter não lida com X-Forwarded-For (IP do proxy atrás de reverse proxy) — documentado

**PENDÊNCIAS:**
- Dashboard HTML (`/dashboard/`) permanece público (read-only) — login UI futura (TASK-010+)
- `get_current_user` não verifica `role` no token (role vem do DB, não do token) — por design
- Rate limiter in-memory não escala para múltiplos workers — aceitável para single-instance

**PRÓXIMA TAREFA:**
TASK-010 — Simulation Engine (`app/simulation/`) + seed de dados sintéticos

---

## TASK-008.1 — Correções Pós-Auditoria (H-02, M-19, L-20, L-21, I-25)

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- **H-02:** `update_recipe` agora envolve toda a modificação de components/operations em try/except com `rollback()` explícito
- **M-19:** Imports do dashboard movidos para o topo de `main.py` (PEP 8)
- **L-20:** `list_materials` padrão `active=True` em vez de `active=None` (retrocompatível com comportamento pré-M-12)
- **L-21:** `order_360()` carrega recipe com `joinedload(components, operations)`, evitando N+1 futuros
- **I-25:** Plotly.js CDN com SRI hash `sha384-OLBgp1GsljhM2TJ+sbHjaiH9txEUvgdDTAzHv2P24donTt6/529l+9Ua0vFImLlb` + `crossorigin="anonymous"`

**ARQUIVOS ALTERADOS:**
- `app/services/production_service.py` — try/except + rollback em `update_recipe`
- `app/main.py` — imports do dashboard no topo
- `app/api/production.py` — `active=True` default
- `app/analytics/service.py` — `joinedload` no `order_360`
- `templates/dashboard/base.html` — SRI hash
- `auditoria.md` — status corrigido para todos os 5 itens

**TESTES:**
```
158 passed in 5.55s
```
- `python -m compileall app` → OK
- `npm run typecheck` → OK
- `npm run lint` → OK

**AUTO REVIEW:**
- Todas as correções são minimamente invasivas
- H-02: padrão try/except usado em outros métodos do service (consistente)
- M-19: imports no topo seguem PEP 8
- L-20: comportamento padrão restaurado (pré-M-12)
- L-21: `joinedload` segue padrão existente em `get_with_material()` e `get_all()`

**SECURITY AUDIT:**
- H-02: rollback explícito previne dados inconsistentes em caso de exceção
- I-25: SRI hash verificado via `openssl dgst -sha384` contra CDN
- Sem novas superfícies de ataque

**PENDÊNCIAS:**
- H-01: Autenticação/Autorização (TASK-009)
- M-14/M-15: Máquinas de estado para ProductionOrder e QualityInspection (TASK-009)
- M-16: Rate limiting (TASK-009)

**PRÓXIMA TAREFA:**
TASK-009 — Autenticação/Autorização + Rate Limiting + Máquinas de Estado

---

## TASK-008 — Dashboard + Correções de Performance (M-09, M-12, M-17, M-18, L-09/L-10, L-17, L-19, I-21)

**Status:** DONE

**Data:** 2026-08-12

**IMPLEMENTADO:**
- **M-09:** `session_dependency()` com rollback automático (captura Exception, faz rollback, re-lança)
- **M-12:** `GET /materials?active=true|false|<omit>` — filtro de status ativo/inativo/todos
- **M-17:** Paginação real (skip/limit) em 4 sub-endpoints: batches/order, resources/work-center, recipes/material, inspections/non-conformities
- **M-18:** `joinedload` em `ProductionOrderRepository.get_all()` (material+recipe) e `ProductionRecipeRepository.get_all()` (components+operations) — elimina N+1
- **L-09/L-10:** `index=True` em `ProductionOrder.status` e `QualityInspection.inspection_status`
- **L-17:** `list_orders_by_status` path param tipado como `ProductionOrderStatus` enum (validação automática 422)
- **L-19:** Helper `paginate()` extraído para `app/domain/common.py` e reutilizado nos 3 routers
- **I-21:** `GET /health` executa `SELECT 1` e retorna `{"status":"ok","database":"connected"}` ou 503
- **Dashboard:**
  - `app/analytics/service.py` — `AnalyticsService` com 8 métodos: `executive_kpis()`, `production_stats()`, `quality_stats()`, `cost_stats()`, `order_360()`, `order_status_distribution()`, `inspection_status_distribution()`, `cost_variance_by_order()`
  - `templates/dashboard/base.html` — Layout base com nav, CSS responsivo
  - `templates/dashboard/home.html` — Dashboard executivo com 6 KPIs + 3 gráficos Plotly (pie orders, pie inspections, bar variance)
  - `templates/dashboard/order_360.html` — Visão integrada PP-PI + QM + CO para uma Production Order
  - `app/api/dashboard.py` — 2 page endpoints (`/dashboard/`, `/dashboard/order-360`) + 5 data API endpoints
- `app/domain/common.py` — `PaginatedResponse[T]` genérico + `paginate()` helper (L-19)

**ARQUIVOS CRIADOS:**
- `app/analytics/service.py`
- `app/api/dashboard.py`
- `templates/dashboard/base.html`
- `templates/dashboard/home.html`
- `templates/dashboard/order_360.html`
- `tests/unit/test_dashboard.py` (15 testes)
- `app/domain/common.py` (PaginatedResponse + paginate helper)

**ARQUIVOS ALTERADOS:**
- `app/database/connection.py` — M-09 rollback
- `app/domain/entities.py` — L-09/L-10 índices
- `app/api/production.py` — L-17 enum, L-19 paginate, M-12 active, M-17 skip/limit
- `app/api/quality.py` — L-19 paginate, M-17 skip/limit
- `app/api/costing.py` — L-19 paginate
- `app/repositories/production_repository.py` — M-12 list_all/inactive, M-17 skip/limit, M-18 joinedload
- `app/repositories/quality_repository.py` — M-17 skip/limit
- `app/services/production_service.py` — M-12 active, L-17 enum, M-17 skip/limit
- `app/services/quality_service.py` — M-17 skip/limit
- `app/main.py` — I-21 health DB check, dashboard routers
- `tests/unit/test_api_production.py` — health test update

**DOCUMENTOS CONSULTADOS:**
- `plano/09-dashboard.md` — layout do dashboard executivo e Order 360°
- `plano/08-integracao-eventos.md` — fluxo integrado PP-PI→QM→CO
- `auditoria.md` — M-09, M-12, M-17, M-18, L-09/L-10, L-17, L-19, I-21

**TESTES:**
```
158 passed in 5.18s
```
- `.venv/bin/python -m compileall app/` → OK
- `.venv/bin/pytest tests/` → **158 passed** (era 143)
- `npm run typecheck` → OK
- `npm run lint` → OK

**AUTO REVIEW:**
- Dashboard é Python-first: dados no backend via SQLAlchemy parametrizado, frontend com Jinja2 + Plotly.js
- AnalyticsService somente leitura (SELECT) — não gerencia transações
- Paginação unificada com helper compartilhado (L-19)
- Performance: N+1 resolvido com `joinedload` (M-18), índices em colunas de status (L-09/L-10)
- Sem overengineering: HTML + CSS inline, sem frameworks JS pesados

**SECURITY AUDIT:**
- SQL injection: ✅ ORM parametrizado em AnalyticsService
- XSS: ✅ `| tojson` escapa; `fetch()` para dados dinâmicos
- Secrets: ✅ Nenhum
- Validação: ✅ Pydantic enums (L-17), query params tipados
- Erros: ✅ EntityNotFoundError retorna 404 genérico
- CORS: N/A — sem endpoints de dados novos que requeiram CORS
- Autenticação: ⚠️ Pendente (TASK-009)

**PENDÊNCIAS:**
- H-01: Autenticação/Autorização (TASK-009)
- H-02: `update_recipe` sem rollback explícito (TASK-008.1)
- M-14/M-15: Transições de estado (TASK-009)
- M-16: Rate limiting (TASK-009)
- M-19: Imports no meio do main.py (TASK-008.1)
- L-20: Default active=None confuso (TASK-008.1)
- L-21: order_360 sem BOM/roteiro (TASK-008.1)
- I-25: Plotly.js sem SRI (TASK-008.1)

**PRÓXIMA TAREFA:**
TASK-008.1 — Correções pós-auditoria (H-02, M-19, L-20, L-21, I-25)

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
| Jinja2 | 3.1.4 | Templates Dashboard |
| Plotly.js | 2.35.2 | Gráficos Dashboard (CDN) |
| Alembic | (latest) | Migrations |
| pytest | 8.3.0 | Testes |
| SQLite | (in-memory) | Testes unitários |

## Estrutura de Diretórios Atual

```
simulador-erp-industrial/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app + routers + exception handlers + /health
│   ├── core/                      # exceptions + logging
│   ├── api/
│   │   ├── __init__.py
│   │   ├── production.py          # PP-PI REST endpoints (23 endpoints)
│   │   ├── quality.py             # QM REST endpoints (9 endpoints)
│   │   ├── costing.py             # CO REST endpoints (6 endpoints)
│   │   └── dashboard.py           # Dashboard pages + API (2 pages + 5 data endpoints)
│   ├── domain/
│   │   ├── common.py              # PaginatedResponse[T] + paginate() helper
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
│   │   ├── production_service.py  # ProductionService (23 métodos)
│   │   ├── quality_service.py     # QualityService (8 métodos)
│   │   └── costing_service.py     # CostingService (7 métodos)
│   ├── analytics/
│   │   └── service.py             # AnalyticsService (8 métodos de agregação)
│   ├── database/
│   │   └── connection.py          # SQLAlchemy engine + session + session_dependency
│   ├── simulation/                # (vazio — TASK-009)
│   └── static/                    # (vazio)
├── templates/
│   └── dashboard/
│       ├── base.html              # Layout base com nav + CSS
│       ├── home.html              # Dashboard Executivo (KPIs + Plotly charts)
│       └── order_360.html         # Order 360° (visão integrada PP-PI/QM/CO)
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
│       ├── test_api_quality.py     # 20 testes de API QM
│       ├── test_api_costing.py     # 15 testes de API CO
│       ├── test_recipes_crud.py    # 15 testes Recipes CRUD
│       └── test_dashboard.py       # 15 testes Analytics + Dashboard API
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
8. **Próximo passo: TASK-009** — Autenticação/Autorização + Rate Limiting + Máquinas de Estado
   - H-01: Implementar JWT/OAuth2 + roles (admin, operator, viewer)
   - M-14/M-15: State machines para ProductionOrder e QualityInspection
   - M-16: Rate limiting (slowapi ou fastapi-limiter)
   - L-14: Cascade delete ProductionOrder→Batches
9. **Status atual:** 158 testes passando, dashboard funcional, todas as correções de performance aplicadas
