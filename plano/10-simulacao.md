# Engine de Simulação

## Execução

```bash
python -m simulation.generate --months 12
```

**Resultado esperado:**
- 12 meses de dados
- ~180 ordens de produção
- ~540 inspeções de qualidade
- ~50,000 registros de dados

## Parâmetros Configuráveis

```yaml
production:
  failure_rate: 0.03
  yield_mean: 0.96

quality:
  inspection_failure_rate: 0.04

maintenance:
  downtime_probability: 0.05
```

## Cenários de Simulação

### Cenário Normal
- Yield: 96%
- Quality: 97%
- Cost variance: +2%

### Cenário de Crise (Causa e Efeito)
```
Machine downtime
      ↓
Production delay
      ↓
Lower yield
      ↓
Quality deviation
      ↓
Rework
      ↓
Higher cost
```

Este cenário demonstra análise de **causa e efeito** em processos industriais — excelente para portfólio.

## Scripts

| Script | Descrição |
|--------|-----------|
| `scripts/generate_data.py` | Gera dados sintéticos |
| `scripts/seed_database.py` | Popula o banco de dados |
| `scripts/reset_database.py` | Reseta o banco para estado limpo |
