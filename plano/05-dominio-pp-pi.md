# Módulo PP-PI — Production Planning

## Entidades

- **Material** — Material produzido (ex: Beer 600ml)
- **Production Recipe** — Receita de produção (BOM + roteiro)
- **Production Order** — Ordem de produção
- **Batch** — Lote produzido
- **Production Confirmation** — Confirmação de produção
- **Material Consumption** — Consumo de materiais
- **Production Resource** — Recurso de produção (máquina, linha)

## Exemplo de Ordem de Produção

```
Production Order: PO-2026-000124

Material:        Beer 600ml
Planned Qty:     10,000 L
Actual Qty:      9,620 L
Batch:           B20260810-001
Resource:        Filler Line 04
Status:          COMPLETED
```

## Indicadores

- Volume de produção
- Ordens de produção (planejadas vs concluídas)
- Yield (rendimento)
- Utilização de máquina
- Variância de produção
- OEE (Overall Equipment Effectiveness)
