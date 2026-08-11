# Módulo QM — Quality Management

## Fluxo de Inspeção

```
Production Order
       │
       ▼
Batch
       │
       ▼
Quality Inspection
       │
 ┌─────┴─────┐
 ▼           ▼
PASS        FAIL
 │           │
 ▼           ▼
Release    Rework
            │
            ▼
         Scrap
```

## Parâmetros de Inspeção (Dados Sintéticos)

- pH
- Alcohol %
- Temperature
- CO2
- Appearance
- Microbiological Status

> **Nota:** Os parâmetros são sintéticos. Não tentar reproduzir valores reais de produção cervejeira com precisão científica. Deixar explícito: *"Synthetic data for educational and simulation purposes."*

## Indicadores

- Inspection lots (lotes inspecionados)
- Pass rate (taxa de aprovação)
- Failure rate (taxa de falha)
- Rework (retrabalho)
- Scrap (refugo)
- Non-conformities (não-conformidades)

## Gatilho

Toda ordem de produção gera automaticamente uma inspeção de qualidade vinculada ao batch.
