# Integração — Modelo de Eventos

## Conceito Central

Os módulos não operam isoladamente. O sistema é orientado a eventos:

```
                  PRODUCTION ORDER
                         │
                         ▼
                  Production Event
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
            PP-PI       QM         CO
              │          │          │
              │          │          │
          produção    inspeção    custos
              │          │          │
              └──────────┼──────────┘
                         ▼
                    LOT / BATCH
                         │
                         ▼
                    Analytics
```

## Fluxo Completo

1. Criação da **Production Order**
2. Disparo do **Production Event**
3. PP-PI: executa produção, gera confirmação, registra consumo
4. QM: gera inspeção vinculada ao batch, avalia parâmetros
5. CO: calcula custos planejados vs reais, calcula variância
6. Se QM = FAIL → CO registra impacto financeiro do retrabalho/scrap
7. Consolidação no **Analytics**

## Por que Eventos?

Demonstra compreensão de sistemas empresariais integrados, onde uma ação em um módulo dispara consequências em outros módulos — exatamente como em um ERP real.
