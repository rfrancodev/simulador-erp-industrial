# Arquitetura de Infraestrutura

## Diagrama de Rede

```
                         INTERNET
                            │
                            ▼
                  ┌───────────────────┐
                  │     CLOUDFLARE    │
                  │ DNS / SSL / WAF   │
                  └─────────┬─────────┘
                            │
                     Cloudflare Tunnel
                            │
                            ▼
                  ┌───────────────────┐
                  │      VPS          │
                  │      Docker       │
                  └─────────┬─────────┘
                            │
          ┌─────────────────┼──────────────────┐
          │                 │                  │
          ▼                 ▼                  ▼
   ┌─────────────┐   ┌─────────────┐   ┌──────────────┐
   │   Nginx /   │   │   Python    │   │ PostgreSQL  │
   │ Reverse     │──▶│ Application │──▶│             │
   │ Proxy       │   │   / API     │   │ ERP Database│
   └─────────────┘   └──────┬──────┘   └──────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ Simulation    │
                    │ Engine        │
                    │ Python        │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ HTML Dashboard│
                    │ Plotly / JS   │
                    └───────────────┘
```

## Infraestrutura Existente (Oracle Cloud VPS)

Aproveitar a VPS atual da Oracle Cloud:

```
Oracle Cloud VPS
│
├── Docker
├── Nginx Proxy Manager
├── PostgreSQL
├── n8n
├── OpenCode
│
└── industrial-erp-simulator
    ├── industrial-erp-api    (container FastAPI)
    └── industrial-erp-db     (schema no PostgreSQL existente)
```

## PostgreSQL — Schema Dedicado

Não criar um novo container PostgreSQL. Usar um schema/database separado no PostgreSQL central:

```
PostgreSQL
│
├── database: industrial_erp
│   ├── schema: pp
│   ├── schema: qm
│   ├── schema: co
│   ├── schema: master_data
│   └── schema: analytics
```

## Cloudflare

**Domínio sugerido:** `erp.francorafael.com`

**Fluxo:**
```
https://erp.francorafael.com
             │
             ▼
        Cloudflare (DNS + SSL)
             │
             ▼
      Cloudflare Tunnel
             │
             ▼
       Oracle VPS
             │
             ▼
     Docker container (FastAPI)
```

## Valor para Portfólio

Demonstra conhecimento em:
- Cloudflare (DNS, SSL)
- Reverse proxy (Nginx Proxy Manager)
- Docker
- Linux
- APIs
- Banco de dados
- Aplicação web full-stack
