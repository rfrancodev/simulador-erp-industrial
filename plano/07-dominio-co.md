# Módulo CO — Controlling / Costing

## Estrutura de Custos por Ordem

Cada ordem de produção possui:

### Planned Cost
- Raw Material (matéria-prima planejada)
- Labor (mão de obra planejada)
- Machine (custo de máquina planejado)
- Energy (energia planejada)

### Actual Cost
- Actual Material (matéria-prima real)
- Actual Labor (mão de obra real)
- Actual Machine Time (tempo real de máquina)
- Losses (perdas)
- Rework (retrabalho)

### Variance
```
Variance = Actual Cost - Planned Cost
```

## Integração QM → CO (Diferencial do Projeto)

```
Production Order
       │
       ▼
Batch B001
       │
       ▼
Quality Inspection
       │
       ▼
FAIL
       │
       ├── Rework
       │
       └── Scrap
              │
              ▼
         Financial Impact
              │
              ▼
        CO Cost Variance
```

### Exemplo de Dashboard CO:
> *"Quality failure generated R$ 8,420 in additional production cost."*

Isso demonstra a relação **operação → qualidade → dinheiro**, que é muito mais valiosa do que simplesmente mostrar "taxa de defeitos: 2.3%".

## Indicadores

- Planned Cost
- Actual Cost
- Variance
- Cost per Liter
- Quality Cost
- Material Cost
- Machine Cost
