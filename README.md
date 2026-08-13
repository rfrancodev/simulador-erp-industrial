# Industrial ERP Simulator

**Integrated PP-PI, QM & CO Process Simulation** — *inspired by SAP S/4HANA concepts.*

> **Disclaimer:** This project is *not* an SAP implementation. It is inspired by
> SAP concepts (PP-PI, QM, CO) for educational and portfolio purposes. All
> industrial data is **synthetic** — for educational and simulation purposes only.

A Python-first platform that demonstrates how production, quality and cost
modules integrate — the relationship **operation → quality → money** — like a
real ERP.

| Module | Description |
|--------|-------------|
| **PP-PI** | Production Planning — materials, recipes (BOM + routing), production orders, batches, resources |
| **QM** | Quality Management — inspections, non-conformities, rework/scrap |
| **CO** | Controlling — planned vs actual costs, variance |

## Features

- **REST API** (FastAPI) with JWT auth + role-based access (admin / operator / viewer)
- **State machines** enforcing valid transitions for production orders and quality inspections
- **Event-driven integration** — creating a batch auto-triggers a quality inspection; completing an order auto-creates a cost record
- **Simulation engine** generating months of synthetic data (normal and crisis scenarios)
- **Dashboard** (Jinja2 + Plotly.js) with executive KPIs, monthly trend and Order 360° view
- **Rate limiting**, account lockout, and SQLAlchemy/Alembic migrations

## Stack

| Technology | Use |
|-----------|-----|
| Python 3.11 | Core language |
| FastAPI | API framework |
| SQLAlchemy 2.0 | ORM |
| Pydantic v2 | Data validation |
| PostgreSQL | Database |
| Alembic | Migrations |
| Jinja2 + Plotly.js | Dashboard |
| PyJWT | Authentication |

## Environment Variables

Configure via `.env` (see `.env.example`):

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT signing key (min 32 bytes in production) |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Local `db` service credentials (Docker Compose) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT expiry (default 30) |
| `RATE_LIMIT_PER_MINUTE` | Per-IP request limit (default 60) |
| `TRUST_PROXY_HEADERS` | Read forwarded IP headers only from trusted proxies |
| `TRUSTED_PROXY_IPS` | Comma-separated trusted proxy IPs/CIDRs |
| `SIM_FAILURE_RATE`, `SIM_YIELD_MEAN`, `SIM_INSPECTION_FAILURE_RATE`, `SIM_DOWNTIME_PROBABILITY` | Simulation defaults |

## Quick Start (Docker)

```bash
cp .env.example .env   # set a strong SECRET_KEY and DB credentials
docker compose up --build
```

The API starts at <http://localhost:8000> (docs at `/docs`, dashboard at `/dashboard`).

Bootstrap an admin user and seed synthetic data:

```bash
docker compose exec api python -m scripts.create_user --username admin --password <secret> --role admin
docker compose exec api python -m scripts.generate_data --months 12 --scenario normal
```

> **Production note:** this project can reuse an existing PostgreSQL instead of
> the local `db` service — override `DATABASE_URL` to point at the shared
> instance (see `plano/02-arquitetura-infraestrutura.md`). For production, set a
> strong `SECRET_KEY`, enable rate limiting (`RATE_LIMIT_PER_MINUTE`) and, if
> behind a reverse proxy, `TRUST_PROXY_HEADERS=true` with a matching
> `TRUSTED_PROXY_IPS` allowlist.

## Local Development (no Docker)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head

python -m scripts.create_user --username admin --password <secret> --role admin
python -m scripts.generate_data --months 12 --scenario normal

uvicorn app.main:app --reload
```

## Usage

- **Login** — `POST /api/auth/login` (OAuth2 form) to obtain a JWT.
- **API** — `/api/production/*`, `/api/quality/*`, `/api/costing/*`, `/api/dashboard/*`.
- **Dashboard** — `/dashboard/` (executive) and `/dashboard/order-360` (integrated view).
- **Simulation** — `scripts/generate_data.py` (see `--help`), `scripts/reset_database.py`.

Roles: `viewer` (read), `operator` (write), `admin` (write + delete + user management).

## Deployment (Production)

Target: Oracle Cloud VPS + Docker + Cloudflare (see `plano/02-arquitetura-infraestrutura.md`).

1. **Database** — reuse a shared PostgreSQL instance (schema/database `industrial_erp`).
2. **Run** the production compose (no local `db` service):

   ```bash
   DATABASE_URL=postgresql://<user>:<pass>@<host>:5432/industrial_erp \
   SECRET_KEY=<random-32-bytes> \
   docker compose -f docker-compose.prod.yml up --build -d
   ```

3. **Reverse proxy** — use Nginx Proxy Manager (or `deploy/nginx.conf.example`) pointing to
    `api:8000`, with sanitized `X-Forwarded-For` headers and a matching
    `TRUSTED_PROXY_IPS` configuration.
4. **Cloudflare** — DNS + SSL (proxy) for the public domain (suggested
   `erp.francorafael.com`), optionally via Cloudflare Tunnel to the VPS.

Bootstrap the admin and seed data on the host:

```bash
docker compose -f docker-compose.prod.yml exec api \
  python -m scripts.create_user --username admin --password <secret> --role admin
docker compose -f docker-compose.prod.yml exec api \
  python -m scripts.generate_data --months 12 --scenario normal
```

## Tests

```bash
pytest                          # unit + integration tests
python -m compileall app/       # static validation
```

## Project Structure

```
app/
├── api/            # REST routers (production, quality, costing, dashboard, auth)
├── domain/         # SQLAlchemy entities + Pydantic schemas + state machines
├── services/       # business logic + event-driven integration
├── repositories/   # data access
├── simulation/     # synthetic data engine
├── analytics/      # dashboard aggregations
├── security/       # JWT, passwords, RBAC
├── core/           # exceptions, logging, event bus
└── middleware/     # rate limiting
database/migrations/   # Alembic migrations
scripts/               # CLI (create_user, generate_data, reset_database)
tests/                 # unit + integration
```

## Documentation

- `docs/` — ARCHITECTURE, BUSINESS_PROCESS, DATA_MODEL, SAP_MAPPING, RUNBOOK
- `plano/` — architecture, domains, integration and simulation planning (source of truth)
- `TASKS.md` — task cycle and history
- `auditoria.md` — security/quality audit reports
- `HANDOFFS.md` — task handoffs
