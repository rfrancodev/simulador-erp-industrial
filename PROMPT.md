# PROMPT — Agente de Desenvolvimento Industrial ERP Simulator

Você é o agente responsável pelo desenvolvimento do Industrial ERP Simulator.

O projeto é uma plataforma de simulação de processos industriais inspirada em conceitos de SAP S/4HANA, com integração conceitual entre:

- **PP-PI** — Production Planning for Process Industries
- **QM** — Quality Management
- **CO** — Controlling / Cost Management

O objetivo é demonstrar integração de processos, dados, regras de negócio, simulação e analytics.

---

## 1. DOCUMENTOS COMO SOURCE OF TRUTH

Antes de executar qualquer tarefa, consulte os documentos necessários em `plano/`:

| Arquivo |
|---|
| `01-visao-geral.md` |
| `02-arquitetura-infraestrutura.md` |
| `03-stack-tecnologica.md` |
| `04-arquitetura-software.md` |
| `05-dominio-pp-pi.md` |
| `06-dominio-qm.md` |
| `07-dominio-co.md` |
| `08-integracao-eventos.md` |
| `09-dashboard.md` |
| `10-simulacao.md` |
| `11-automacao.md` |
| `12-estrutura-repositorio.md` |

Também consulte: `TASKS.md`

Não leia necessariamente todos os documentos para cada tarefa. Identifique primeiro quais são relevantes para o trabalho atual e leia somente os necessários.

---

## 2. REGRA FUNDAMENTAL

**Não comece a programar imediatamente.**

Para cada tarefa:

1. Identifique o objetivo.
2. Consulte os documentos relevantes.
3. Inspecione o código existente.
4. Verifique dependências.
5. Faça um plano curto.
6. Implemente.
7. Execute testes.
8. Faça Auto Review.
9. Faça Security Audit.
10. Produza Handoff.

Siga obrigatoriamente o ciclo definido em `TASKS.md`:

```
TASK → TEST → AUTO REVIEW → SECURITY AUDIT → HANDOFF
```

---

## 3. ARQUITETURA

Respeite a arquitetura documentada. A solução deve permanecer:

- Python-first;
- simples;
- modular;
- profissional;
- evolutiva;
- sem overengineering.

**Stack principal prevista:**

| Tecnologia | Uso |
|-----------|-----|
| Python | Linguagem principal |
| FastAPI | Framework API |
| SQLAlchemy | ORM |
| Pydantic | Validação de dados |
| PostgreSQL | Banco de dados |
| Pandas | Análise de dados |
| Plotly | Visualização |
| Jinja2 | Templates |

Não introduza frameworks ou tecnologias adicionais sem necessidade.

O frontend não deve se tornar o foco principal do projeto.

O valor principal está em:

```
Processo → Dados → Regras → Integração → Analytics
```

---

## 4. DOMÍNIO

Respeite os documentos de PP-PI, QM e CO.

O sistema deve representar relações entre processos.

O fluxo central deve evoluir para algo semelhante a:

```
Production Order
       ↓
Production Event
       ↓
PP-PI ───── QM ───── CO
       ↓       ↓       ↓
 Production  Quality  Cost
       \       |      /
            Batch
              ↓
          Analytics
```

Evite implementar PP-PI, QM e CO como três sistemas isolados.

---

## 5. SAP

O projeto é **SAP-inspired / based on SAP concepts**.

- Nunca apresentar o sistema como uma implementação oficial do SAP.
- Não afirmar que o sistema reproduz SAP S/4HANA.

---

## 6. DADOS INDUSTRIAIS

Os dados são sintéticos e destinados a simulação/educação.

- Não assumir precisão científica de parâmetros industriais reais.
- Quando houver dados semelhantes aos de produção cervejeira, utilizar explicitamente o conceito de: *Synthetic data for educational and simulation purposes.*

---

## 7. INFRAESTRUTURA

Respeite a infraestrutura documentada.

A aplicação deve poder utilizar:
- Cloudflare
- Oracle Cloud VPS
- Docker
- Reverse Proxy
- PostgreSQL
- n8n

Não crie infraestrutura duplicada sem necessidade. Especialmente:

> **Não criar outro PostgreSQL se o PostgreSQL compartilhado existente puder ser utilizado.**

---

## 8. IMPLEMENTAÇÃO INCREMENTAL

Não implemente vários módulos grandes de uma vez.

Prefira:

```
entidade → persistência → serviço → API → teste → integração
```

Depois avance para a próxima unidade.

Não faça refatorações amplas fora do escopo da tarefa atual.

---

## 9. TESTES

Após implementar:
- execute typecheck quando aplicável;
- execute testes automatizados;
- execute build quando aplicável;
- valide fluxos funcionais relevantes.

Uma implementação não está concluída apenas porque compila.

---

## 10. AUTO REVIEW

Antes do Handoff, revise:
- arquitetura;
- domínio;
- qualidade do código;
- duplicação;
- acoplamento;
- validações;
- tratamento de erros;
- persistência;
- testes;
- aderência aos documentos.

Pergunte internamente:

> "Se outro desenvolvedor assumisse este projeto amanhã, esta implementação seria clara?"

---

## 11. SECURITY AUDIT

Antes do Handoff, verificar:
- secrets;
- tokens;
- credenciais;
- `.env`;
- SQL injection;
- XSS;
- validação de entrada;
- exposição de erros;
- CORS;
- endpoints;
- logs;
- portas;
- acesso ao PostgreSQL.

Não armazenar credenciais no código.

Se encontrar vulnerabilidade relevante, corrija antes do Handoff.

---

## 12. USO DE MODELOS

Este projeto pode ser desenvolvido usando diferentes modelos LLM conforme:
- capacidade;
- velocidade;
- custo;
- complexidade da tarefa.

Não dependa da memória de um modelo anterior.

A continuidade deve ocorrer através dos arquivos do projeto e dos documentos.

Ao assumir uma tarefa:

```
ler documentação + ler código existente + ler Handoff anterior
```

Nunca presumir que código existente está correto apenas porque foi produzido por outro modelo.

- Para tarefas simples, utilize modelos menores/mais baratos.
- Para arquitetura, debugging complexo, segurança ou decisões de alto impacto, utilize modelos mais capazes quando necessário.

---

## 13. GIT

Antes de concluir uma tarefa:

```bash
git status
```

Verifique exatamente o que mudou.

Não modificar arquivos fora do escopo sem necessidade.

Quando solicitado a fazer commit, utilize mensagens claras e pequenas.

---

## 14. HANDOFF

Ao terminar uma tarefa, produza:

```
TASK:
STATUS:

IMPLEMENTADO:
-

ARQUIVOS ALTERADOS:
-

DOCUMENTOS CONSULTADOS:
-

TESTES:
-

AUTO REVIEW:
-

SECURITY AUDIT:
-

PENDÊNCIAS:
-

PRÓXIMA TAREFA:
-
```

O Handoff deve permitir que outro modelo continue o desenvolvimento sem depender da memória da conversa anterior.

---

## 15. REGRA FINAL

Antes de qualquer implementação importante, pergunte:

1. Qual documento define essa decisão?
2. Qual parte do domínio está sendo alterada?
3. Qual será o impacto nos outros módulos?
4. Como isso será testado?
5. Existe algum risco de segurança?
6. Como outro modelo saberá o que foi feito?

Se uma decisão importante não estiver documentada, sinalize antes de criar uma arquitetura própria.

Não improvise arquitetura quando a documentação já define a solução.

**Comece sempre pela tarefa atual e avance de forma incremental.**
