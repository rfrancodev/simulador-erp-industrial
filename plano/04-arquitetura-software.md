# Arquitetura de Software

## Estrutura do Projeto Python

```
app/
│
├── main.py                     # Entry point FastAPI
│
├── api/                        # Rotas / endpoints
│   ├── production.py
│   ├── quality.py
│   ├── costing.py
│   └── dashboard.py
│
├── domain/                     # Modelos de domínio
│   ├── production/
│   ├── quality/
│   └── costing/
│
├── services/                   # Lógica de negócio
│   ├── production_service.py
│   ├── quality_service.py
│   ├── costing_service.py
│   └── simulation_service.py
│
├── repositories/               # Acesso a dados
│   ├── production_repository.py
│   ├── quality_repository.py
│   └── costing_repository.py
│
├── simulation/                 # Engine de simulação
│   ├── production_generator.py
│   ├── quality_generator.py
│   └── cost_generator.py
│
├── analytics/                  # Métricas e indicadores
│   ├── production_metrics.py
│   ├── quality_metrics.py
│   └── cost_metrics.py
│
├── templates/                  # Templates Jinja2
│   ├── dashboard.html
│   ├── production.html
│   ├── quality.html
│   └── costing.html
│
└── static/                     # Assets estáticos
    ├── css/
    └── js/
```

## Princípios

- **Sem overengineering** — arquitetura limpa sem complexidade desnecessária
- **Separação por responsabilidade** — API, domain, services, repositories
- **Simulação isolada** — engine de simulação separada da aplicação web
- **Analytics independente** — métricas extraídas como camada separada
