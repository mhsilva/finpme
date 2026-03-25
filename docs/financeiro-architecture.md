# Módulo Financeiro — Arquitetura

SaaS FinPME — plano de expansão do core financeiro com 6 sub-módulos.

---

## Status atual (o que já existe)

| Componente | Status |
|---|---|
| Transações (OFX/CSV/NF-e XML) + categorização IA | ✅ Pronto |
| DRE + Fluxo de Caixa + cache Redis | ✅ Pronto |
| Agente com Tool Use + SSE streaming | ✅ Pronto |
| Confirmação de pagamentos | ✅ Pronto |
| Contas a pagar/receber | ❌ Fase 2 |
| Conciliação bancária | ❌ Fase 3 |
| Empréstimos/linhas de crédito | ❌ Fase 4 |
| Cartões corporativos | ❌ Fase 4 |
| Tesouraria (projeção 90 dias) | ❌ Fase 5 |
| Centro de custo | ❌ Fase 1 |

---

## Banco de Dados — Novas Tabelas

Migration `supabase/migrations/002_financeiro.sql`

```sql
-- ─── CENTROS DE CUSTO ─────────────────────────────────────────────
CREATE TABLE cost_centers (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   UUID NOT NULL REFERENCES tenants(id),
  name        TEXT NOT NULL,          -- "Marketing", "TI", "Projeto Alfa"
  code        TEXT NOT NULL,          -- "MKT", "TI001"
  parent_id   UUID REFERENCES cost_centers(id),  -- hierarquia
  type        TEXT DEFAULT 'department',  -- department | project | product
  budget      NUMERIC(15,2),          -- orçamento mensal
  active      BOOLEAN DEFAULT true,
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- Rateio N:N (uma transação pode ser dividida entre CCs)
CREATE TABLE transaction_cost_centers (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL,
  transaction_id  UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
  cost_center_id  UUID NOT NULL REFERENCES cost_centers(id),
  percentage      NUMERIC(5,2) DEFAULT 100.00,
  amount          NUMERIC(15,2) NOT NULL,
  created_at      TIMESTAMPTZ DEFAULT now()
);

-- ─── CONTAS BANCÁRIAS ──────────────────────────────────────────────
CREATE TABLE bank_accounts (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      UUID NOT NULL REFERENCES tenants(id),
  name           TEXT NOT NULL,    -- "Conta Corrente Itaú 1234"
  bank_code      TEXT,             -- ISPB/COMPE
  branch         TEXT,
  account_number TEXT,
  type           TEXT DEFAULT 'checking',  -- checking | savings | payment
  balance        NUMERIC(15,2) DEFAULT 0,
  balance_date   DATE,
  active         BOOLEAN DEFAULT true,
  created_at     TIMESTAMPTZ DEFAULT now()
);

-- ─── CONTAS A PAGAR / RECEBER ──────────────────────────────────────
CREATE TABLE payables_receivables (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID NOT NULL REFERENCES tenants(id),
  type                TEXT NOT NULL,    -- 'payable' | 'receivable'
  description         TEXT NOT NULL,
  amount              NUMERIC(15,2) NOT NULL,
  due_date            DATE NOT NULL,
  paid_date           DATE,
  status              TEXT DEFAULT 'pending',  -- pending | paid | overdue | partial | cancelled
  contact_name        TEXT,
  contact_doc         TEXT,             -- CPF/CNPJ
  bank_account_id     UUID REFERENCES bank_accounts(id),
  cost_center_id      UUID REFERENCES cost_centers(id),
  installments_total  INT DEFAULT 1,
  installments_num    INT DEFAULT 1,
  parent_id           UUID REFERENCES payables_receivables(id),
  recurrence          TEXT,             -- monthly | weekly | yearly | NULL
  transaction_id      UUID REFERENCES transactions(id),  -- conciliação
  collection_rule_id  UUID,
  last_notified_at    TIMESTAMPTZ,
  notes               TEXT,
  created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON payables_receivables(tenant_id, due_date, status);

-- Régua de cobrança
CREATE TABLE collection_rules (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   UUID NOT NULL REFERENCES tenants(id),
  name        TEXT NOT NULL,
  is_default  BOOLEAN DEFAULT false,
  -- Ex: [{days: -3, channel: "email"}, {days: 0, channel: "email"}, {days: 3, channel: "whatsapp"}]
  steps       JSONB NOT NULL DEFAULT '[]',
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- ─── CONCILIAÇÃO BANCÁRIA ──────────────────────────────────────────
CREATE TABLE reconciliation_matches (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             UUID NOT NULL,
  transaction_id        UUID NOT NULL REFERENCES transactions(id),
  payable_receivable_id UUID REFERENCES payables_receivables(id),
  bank_account_id       UUID REFERENCES bank_accounts(id),
  matched_by            TEXT DEFAULT 'auto',  -- auto | manual
  confidence            NUMERIC(4,3),
  created_at            TIMESTAMPTZ DEFAULT now(),
  UNIQUE(transaction_id)
);

-- ─── EMPRÉSTIMOS E LINHAS DE CRÉDITO ──────────────────────────────
CREATE TABLE credit_facilities (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      UUID NOT NULL REFERENCES tenants(id),
  name           TEXT NOT NULL,
  type           TEXT NOT NULL,  -- loan | credit_line | overdraft | antecipacao_recebiveis
  bank           TEXT,
  total_amount   NUMERIC(15,2) NOT NULL,
  used_amount    NUMERIC(15,2) DEFAULT 0,
  interest_rate  NUMERIC(8,4),   -- taxa mensal %
  interest_type  TEXT DEFAULT 'pre',  -- pre | pos
  start_date     DATE,
  end_date       DATE,
  status         TEXT DEFAULT 'active',  -- active | paid | suspended
  notes          TEXT,
  created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE loan_installments (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID NOT NULL,
  credit_facility_id  UUID NOT NULL REFERENCES credit_facilities(id),
  installment_number  INT NOT NULL,
  due_date            DATE NOT NULL,
  principal           NUMERIC(15,2),
  interest            NUMERIC(15,2),
  total               NUMERIC(15,2) NOT NULL,
  paid_date           DATE,
  status              TEXT DEFAULT 'pending',  -- pending | paid | overdue
  transaction_id      UUID REFERENCES transactions(id),
  created_at          TIMESTAMPTZ DEFAULT now()
);

-- ─── CARTÕES CORPORATIVOS ──────────────────────────────────────────
CREATE TABLE corporate_cards (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL REFERENCES tenants(id),
  name          TEXT NOT NULL,
  holder_name   TEXT,
  last_digits   CHAR(4),
  brand         TEXT,       -- visa | mastercard | elo | amex
  bank          TEXT,
  credit_limit  NUMERIC(15,2),
  closing_day   INT,        -- dia do fechamento
  due_day       INT,        -- dia do vencimento
  cost_center_id UUID REFERENCES cost_centers(id),
  status        TEXT DEFAULT 'active',  -- active | blocked | cancelled
  created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE card_statements (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL,
  card_id         UUID NOT NULL REFERENCES corporate_cards(id),
  reference_month DATE NOT NULL,
  closing_date    DATE NOT NULL,
  due_date        DATE NOT NULL,
  total_amount    NUMERIC(15,2) DEFAULT 0,
  paid_amount     NUMERIC(15,2) DEFAULT 0,
  status          TEXT DEFAULT 'open',  -- open | closed | paid
  created_at      TIMESTAMPTZ DEFAULT now()
);
```

---

## Arquitetura Backend

```
backend/
  routers/
    financeiro/
      __init__.py
      payables.py          # CRUD contas a pagar/receber + parcelamento
      conciliacao.py       # Conciliação bancária (sugestão + confirmar)
      credito.py           # Empréstimos + parcelas + simulador
      cartoes.py           # Cartões corporativos + faturas
      centros_custo.py     # CRUD centros de custo + rateio
      tesouraria.py        # Projeção 90 dias multi-cenário

  services/
    financeiro/
      conciliacao_engine.py    # Algoritmo de matching (valor + data + descrição fuzzy)
      cobranca_engine.py       # Régua de cobrança (background task)
      treasury_projector.py    # Projeção de caixa multi-cenário
      custo_rateio.py          # Rateio de transações em centros de custo
```

### Endpoints

```
# Centros de Custo
GET    /financeiro/centros-custo
POST   /financeiro/centros-custo
PATCH  /financeiro/centros-custo/{id}
DELETE /financeiro/centros-custo/{id}
GET    /financeiro/centros-custo/{id}/relatorio?inicio=&fim=   # gastos vs. orçamento

# Contas a P/R
GET    /financeiro/contas?type=payable&status=pending&inicio=&fim=
POST   /financeiro/contas                  # suporta parcelamento (gera N registros)
PATCH  /financeiro/contas/{id}
POST   /financeiro/contas/{id}/pagar       # marca pago + vincula transaction_id

# Conciliação
GET    /financeiro/conciliacao/sugestoes   # auto-match não confirmados
POST   /financeiro/conciliacao/confirmar   # {transaction_id, payable_id}
POST   /financeiro/conciliacao/rejeitar

# Crédito
GET    /financeiro/credito
POST   /financeiro/credito
GET    /financeiro/credito/{id}/parcelas
POST   /financeiro/credito/simular         # simula SAC/Price

# Cartões
GET    /financeiro/cartoes
GET    /financeiro/cartoes/{id}/fatura/{mes}
POST   /financeiro/cartoes/{id}/fechar-fatura

# Tesouraria
GET    /financeiro/tesouraria/projecao?dias=90
```

### Lógica da Projeção de Tesouraria

```python
"""
Fontes para projeção:
  1. Saldo atual confirmado (transações até hoje)
  2. Contas a receber pendentes (por due_date)
  3. Contas a pagar pendentes (por due_date)
  4. Parcelas de empréstimos futuras
  5. Faturas de cartão a vencer
  6. Recorrentes detectados por padrão histórico

Cenários:
  - Otimista:   100% recebíveis entram na data
  - Realista:   80% pontualidade (padrão PME)
  - Pessimista: 60% pontualidade + atraso médio de 15 dias
"""
```

### Novos Agent Tools

```python
projecao_tesouraria(dias=90)             # projeção multi-cenário
listar_contas_pagar(inicio, fim)         # vencimentos futuros
listar_contas_receber(inicio, fim)       # recebíveis futuros
resumo_centro_custo(cc_id, inicio, fim)  # gastos vs. orçamento
alertas_financeiros()                    # contas vencidas, caixa negativo projetado
```

---

## Arquitetura Frontend

```
frontend/src/pages/financeiro/
  contas.js          # Timeline de vencimentos (calendário + lista)
  conciliacao.js     # Split panel: extrato bancário ↔ contas P/R
  credito.js         # Cards de empréstimos + tabela de parcelas
  cartoes.js         # Cards por cartão + fatura mensal
  tesouraria.js      # Gráfico de linha 90 dias (3 cenários)
  centros_custo.js   # Tabela de CCs + barra de orçamento vs. realizado
```

### Sidebar atualizada

```
Dashboard
Lançamentos
── Financeiro ──
  Contas P/R
  Conciliação
  Crédito
  Cartões
  Tesouraria
  Centros de Custo
────────────────
Relatórios
Upload
Chat IA
```

---

## Fases de Implementação

### Fase 1 — Centros de Custo (branch: `feat/financeiro-fase1`)
**Por que começar aqui:** CRUD simples, zero risco de regressão, a FK `cost_center_id` é usada em todas as fases seguintes.

- [ ] Migration `002_financeiro.sql` com todas as tabelas
- [ ] RLS policies nas novas tabelas
- [ ] `routers/financeiro/centros_custo.py` — CRUD completo
- [ ] Campo `cost_center_id` em transações (+ endpoint PATCH)
- [ ] `frontend/src/pages/financeiro/centros_custo.js` — lista, criar, editar, orçamento
- [ ] Relatório de gastos por CC (endpoint + visualização)
- [ ] Agent tool `resumo_centro_custo`

### Fase 2 — Contas a Pagar/Receber
- CRUD completo com parcelamento automático
- Página com timeline/calendário de vencimentos
- Background task que marca `overdue` diariamente
- Régua de cobrança: config de steps

### Fase 3 — Conciliação Bancária
- Algoritmo de auto-match: `|amount_diff| < 0.01` + `date_diff <= 3 dias` + similaridade de descrição
- UI split-panel drag-and-drop ou click para confirmar match

### Fase 4 — Crédito & Cartões
- Gestão de empréstimos + simulador SAC/Price
- Geração automática de parcelas ao cadastrar
- Controle de cartões + faturas mensais
- Link parcelas/faturas ↔ transações importadas

### Fase 5 — Tesouraria
- `treasury_projector.py` com 3 cenários
- Gráfico de linha interativo (30/60/90 dias)
- Alerta: "caixa negativo projetado em DD/MM"
- Agent tool `projecao_tesouraria`

### Fase 6 — Agent Intelligence
- Todos os novos agent tools integrados
- System prompt atualizado com novas capacidades
- Casos de uso:
  - *"Tenho caixa pra pagar o salário semana que vem?"*
  - *"Quanto o marketing consumiu esse trimestre vs. orçamento?"*
  - *"Qual minha exposição em dívida bancária?"*

---

## Estimativa de esforço

| Fase | Backend | Frontend | Total |
|---|---|---|---|
| 1 — Centros de Custo | 1d | 1d | ~2d |
| 2 — Contas P/R | 2d | 2d | ~4d |
| 3 — Conciliação | 2d | 1.5d | ~3.5d |
| 4 — Crédito & Cartões | 2d | 2d | ~4d |
| 5 — Tesouraria | 1.5d | 2d | ~3.5d |
| 6 — Agent | 1d | 0.5d | ~1.5d |
| **Total** | | | **~18 dias úteis** |
