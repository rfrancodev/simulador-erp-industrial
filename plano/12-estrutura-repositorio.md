# Estrutura do Repositório

```
industrial-erp-simulator/
│
├── README.md
├── LICENSE
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── BUSINESS_PROCESS.md
│   ├── DATA_MODEL.md
│   ├── SAP_MAPPING.md
│   └── RUNBOOK.md
│
├── app/
│   ├── main.py
│   ├── api/
│   ├── domain/
│   ├── services/
│   ├── repositories/
│   ├── simulation/
│   ├── analytics/
│   ├── templates/
│   └── static/
│
├── database/
│   ├── migrations/
│   └── seeds/
│
├── scripts/
│   ├── generate_data.py
│   ├── seed_database.py
│   └── reset_database.py
│
└── tests/
    ├── unit/
    └── integration/
```

## Documentação (docs/)

| Arquivo | Conteúdo |
|---------|----------|
| `ARCHITECTURE.md` | Arquitetura técnica do sistema |
| `BUSINESS_PROCESS.md` | Descrição dos processos de negócio |
| `DATA_MODEL.md` | Modelo de dados (entidades, relacionamentos) |
| `SAP_MAPPING.md` | Mapeamento conceitual para SAP S/4HANA |
| `RUNBOOK.md` | Como rodar, implantar e manter o projeto |
