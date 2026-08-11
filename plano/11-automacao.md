# Automação e Analytics Externo

## Integração n8n (Opcional)

```
Python Simulation
       │
       ▼
PostgreSQL
       │
       ▼
n8n
       │
       ├── Detect critical deviation
       │
       ├── Generate notification
       │
       └── Trigger report
```

Exemplo de fluxo:
```
Quality failure > 5%
          ↓
       n8n
          ↓
Alert: "Quality failure rate exceeded threshold"
```

Conecta: **SAP concepts + Python + PostgreSQL + n8n + Cloudflare + Docker**

## Integração Power BI (Opcional)

```
                    PostgreSQL
                        │
             ┌──────────┴──────────┐
             ▼                     ▼
       Python Dashboard       Power BI
             │                     │
        Operacional            Analítico
        / Demonstrativo        / Executivo
```

- **Python Dashboard** — produto principal, operacional/demonstrativo
- **Power BI** — segundo consumidor dos mesmos dados, analítico/executivo

Demonstra que o projeto não depende de uma ferramenta específica para analisar os dados — os dados estão no PostgreSQL e podem ser consumidos por qualquer ferramenta.
