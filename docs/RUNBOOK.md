# Runbook

How to run, deploy and maintain the Industrial ERP Simulator.

## Local development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m scripts.create_user --username admin --password <secret> --role admin
python -m scripts.generate_data --months 12 --scenario normal
uvicorn app.main:app --reload
```

## Docker (development)

```bash
cp .env.example .env   # set SECRET_KEY + POSTGRES_* credentials
docker compose up --build
docker compose exec api python -m scripts.create_user --username admin --password <secret> --role admin
docker compose exec api python -m scripts.generate_data --months 12 --scenario normal
```

## Production deployment

Target: Oracle Cloud VPS + Docker + Cloudflare (see `plano/02`).

### 1. Database

Use the externally-managed PostgreSQL container `industrial-erp-postgres`
(database `industrial_erp`, app user `industrial_app`), published on the host
loopback `127.0.0.1:5432`.

### 2. Application

Copy `.env.example` to `.env` and set `DATABASE_URL` plus a strong `SECRET_KEY`
(never commit the real `.env`). Then:

```bash
cp .env.example .env
docker compose -f docker-compose.prod.yml up --build -d
```

The API runs with `network_mode: host` so it can reach the PostgreSQL on the
host loopback, and binds to `127.0.0.1:8000` (not exposed publicly).

### 3. Reverse proxy

Use Nginx Proxy Manager (UI) or `deploy/nginx.conf.example` pointing to
`127.0.0.1:8000`, forwarding `X-Forwarded-For`.

### 4. Domain — `erp.francorafael.com` (Cloudflare)

The domain `francorafael.com` is already on Cloudflare. Using the subdomain
`erp.francorafael.com` is fully supported:

- **DNS record** — in Cloudflare → DNS, add a record named `erp`:
  - **Option A (proxy)**: `CNAME` → `francorafael.com` (orange cloud), or `A` → VPS public IP.
  - **Option B (Tunnel)**: Cloudflare Zero Trust → Networks → Tunnels → create a
    tunnel (installs `cloudflared` on the VPS) → route `erp.francorafael.com` →
    `http://localhost:8000`. No public ports needed.
- **SSL** — Cloudflare Universal SSL covers `*.francorafael.com` automatically;
  no certificate management on the VPS.
- **WAF/DDoS** — enabled by the orange-cloud proxy.

### 5. Bootstrap data

```bash
docker compose -f docker-compose.prod.yml exec api \
  python -m scripts.create_user --username admin --password <secret> --role admin
docker compose -f docker-compose.prod.yml exec api \
  python -m scripts.generate_data --months 12 --scenario normal
```

## Maintenance

| Task | Command |
|------|---------|
| Apply migrations | `alembic upgrade head` |
| Generate migration | `alembic revision --autogenerate -m "..."` |
| Seed synthetic data | `python -m scripts.generate_data --months 12 [--scenario crisis]` |
| Reset domain data | `python -m scripts.reset_database --yes` |
| Create user | `python -m scripts.create_user --username <u> --role <r>` |
| Reset password | see "User administration" below |
| Run tests | `pytest` |
| Static validation | `python -m compileall app/` |
| Logs (prod) | `docker compose -f docker-compose.prod.yml logs -f api` |

## User administration

Users are stored in the `users` table (see `docs/DATA_MODEL.md`). Production
dashboard access uses a JWT session cookie (`access_token`) issued by
`POST /dashboard/login`.

**Current production user (dashboard):**

| username | role | is_active |
|----------|------|-----------|
| `audit_admin` | `admin` | true |

Never store or commit real passwords. Bootstrap accounts with
`scripts.create_user`; reset an existing password with the procedure below.

### Reset a user password

There is no CLI for reset — the hash uses PBKDF2-HMAC-SHA256 (pure stdlib,
`app/security/passwords.py`, format `pbkdf2_sha256$600000$<salt_hex>$<hash_hex>`).
Reset via SQL with a hash generated off-process:

```bash
# 1. Generate a strong random password and its hash (in memory, never logged):
NEW_HASH=$(python3 -c '
import secrets, string, hashlib
password = "".join(secrets.choice(string.ascii_letters + string.digits + "!@#$%^&*") for _ in range(24))
salt = secrets.token_bytes(16)
digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600000)
print(f"pbkdf2_sha256$600000${salt.hex()}${digest.hex()}")
')

# 2. Update only password_hash for the target user (do not print the password):
PGPASSWORD='<db_password>' psql -h 127.0.0.1 -U industrial_app -d industrial_erp \
  -c "UPDATE users SET password_hash = '${NEW_HASH}' WHERE username = 'audit_admin';"

# 3. Deliver the new password to the user once; change it after first login.
```

Rules: update **only** `password_hash` (never username/role/is_active), do not
write the password to files/logs, and do not rotate `SECRET_KEY` (tokens already
issued would stop validating). After reset, login at
`https://erp.francorafael.com/dashboard/login`.

## Security checklist (production)

- [ ] `SECRET_KEY` ≥ 32 random bytes
- [ ] Strong `DATABASE_URL` credentials (never commit `.env`)
- [ ] `TRUST_PROXY_HEADERS=true` with `TRUSTED_PROXY_IPS` matching the proxy
- [ ] Rate limiting configured (`RATE_LIMIT_PER_MINUTE`)
- [ ] Cloudflare proxy enabled (WAF/DDoS)
- [ ] API port 8000 is bound only to localhost or an internal Docker network
