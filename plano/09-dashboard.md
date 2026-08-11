# Dashboard

## Tecnologia

HTML + CSS + JavaScript + Plotly.js + Jinja2 (templates server-side).

## Home — Dashboard Executivo

```
┌───────────────────────────────────────────────┐
│ INDUSTRIAL ERP SIMULATOR                      │
│ PP-PI | QM | CO                               │
├─────────────┬─────────────┬─────────────────┤
│ Production  │ Quality     │ Cost             │
│ 1.24M L     │ 97.4%       │ R$ 428K          │
├─────────────┼─────────────┼─────────────────┤
│ OEE         │ Scrap       │ Cost Variance    │
│ 82.7%       │ 1.8%        │ +4.2%            │
└─────────────┴─────────────┴─────────────────┘
```

## Telas por Módulo

### Production
- Production Volume
- Production Orders
- Yield
- Machine Utilization
- Production Variance

### Quality
- Inspection Lots
- Pass Rate
- Failure Rate
- Rework
- Scrap
- Non-Conformities

### Cost
- Planned Cost
- Actual Cost
- Variance
- Cost per Liter
- Quality Cost
- Material Cost
- Machine Cost

## Order 360° (Tela Diferencial)

O usuário informa uma **Production Order** (ex: PO-2026-00124) e o sistema mostra a visão integrada:

```
┌──────────────────────────────────────────┐
│ PO-2026-00124                            │
│ Beer 600ml                               │
│ Batch B20260810-001                      │
├──────────────────────────────────────────┤
│ PP-PI                                    │
│ Planned: 10,000 L                        │
│ Actual:   9,620 L                        │
│ Yield:    96.2%                          │
├──────────────────────────────────────────┤
│ QM                                       │
│ pH: 4.21                                 │
│ Status: PASSED                           │
├──────────────────────────────────────────┤
│ CO                                       │
│ Planned Cost: R$ 21,400                  │
│ Actual Cost:  R$ 22,180                  │
│ Variance:      +R$ 780                   │
└──────────────────────────────────────────┘
```

Esta tela demonstra compreensão de **integração de processos** — o verdadeiro valor de um ERP.
