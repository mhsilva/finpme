-- ============================================================
-- FinPME – Migration 002: Módulo Financeiro
-- Centros de custo, contas P/R, conciliação, crédito e cartões
-- ============================================================

-- ─── CENTROS DE CUSTO ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.cost_centers (
  id          UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   UUID          NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  name        TEXT          NOT NULL,
  code        TEXT          NOT NULL,
  parent_id   UUID          REFERENCES public.cost_centers(id),
  type        TEXT          NOT NULL DEFAULT 'department'
                            CHECK (type IN ('department', 'project', 'product')),
  budget      NUMERIC(15,2),
  active      BOOLEAN       NOT NULL DEFAULT true,
  created_at  TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cost_centers_tenant ON public.cost_centers (tenant_id);

-- Rateio N:N (uma transação pode ser dividida entre múltiplos CCs)
CREATE TABLE IF NOT EXISTS public.transaction_cost_centers (
  id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID          NOT NULL,
  transaction_id  UUID          NOT NULL REFERENCES public.transactions(id) ON DELETE CASCADE,
  cost_center_id  UUID          NOT NULL REFERENCES public.cost_centers(id) ON DELETE CASCADE,
  percentage      NUMERIC(5,2)  NOT NULL DEFAULT 100.00
                                CHECK (percentage > 0 AND percentage <= 100),
  amount          NUMERIC(15,2) NOT NULL,
  created_at      TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tcc_tenant_cc ON public.transaction_cost_centers (tenant_id, cost_center_id);
CREATE INDEX IF NOT EXISTS idx_tcc_transaction  ON public.transaction_cost_centers (transaction_id);

-- ─── CONTAS BANCÁRIAS ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.bank_accounts (
  id             UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      UUID          NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  name           TEXT          NOT NULL,
  bank_code      TEXT,
  branch         TEXT,
  account_number TEXT,
  type           TEXT          NOT NULL DEFAULT 'checking'
                               CHECK (type IN ('checking', 'savings', 'payment')),
  balance        NUMERIC(15,2) NOT NULL DEFAULT 0,
  balance_date   DATE,
  active         BOOLEAN       NOT NULL DEFAULT true,
  created_at     TIMESTAMPTZ   DEFAULT NOW()
);

-- ─── CONTAS A PAGAR / RECEBER ──────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.payables_receivables (
  id                  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID          NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  type                TEXT          NOT NULL CHECK (type IN ('payable', 'receivable')),
  description         TEXT          NOT NULL,
  amount              NUMERIC(15,2) NOT NULL,
  due_date            DATE          NOT NULL,
  paid_date           DATE,
  status              TEXT          NOT NULL DEFAULT 'pending'
                                    CHECK (status IN ('pending', 'paid', 'overdue', 'partial', 'cancelled')),
  contact_name        TEXT,
  contact_doc         TEXT,
  bank_account_id     UUID          REFERENCES public.bank_accounts(id),
  cost_center_id      UUID          REFERENCES public.cost_centers(id),
  installments_total  INT           NOT NULL DEFAULT 1,
  installments_num    INT           NOT NULL DEFAULT 1,
  parent_id           UUID          REFERENCES public.payables_receivables(id),
  recurrence          TEXT          CHECK (recurrence IN ('monthly', 'weekly', 'yearly')),
  transaction_id      UUID          REFERENCES public.transactions(id),
  collection_rule_id  UUID,
  last_notified_at    TIMESTAMPTZ,
  notes               TEXT,
  created_at          TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pr_tenant_due ON public.payables_receivables (tenant_id, due_date, status);

-- Régua de cobrança
CREATE TABLE IF NOT EXISTS public.collection_rules (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   UUID        NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  name        TEXT        NOT NULL,
  is_default  BOOLEAN     NOT NULL DEFAULT false,
  -- [{days: -3, channel: "email"}, {days: 0, channel: "email"}, {days: 3, channel: "whatsapp"}]
  steps       JSONB       NOT NULL DEFAULT '[]',
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─── CONCILIAÇÃO BANCÁRIA ──────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.reconciliation_matches (
  id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             UUID        NOT NULL,
  transaction_id        UUID        NOT NULL REFERENCES public.transactions(id),
  payable_receivable_id UUID        REFERENCES public.payables_receivables(id),
  bank_account_id       UUID        REFERENCES public.bank_accounts(id),
  matched_by            TEXT        NOT NULL DEFAULT 'auto' CHECK (matched_by IN ('auto', 'manual')),
  confidence            NUMERIC(4,3),
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (transaction_id)
);

-- ─── EMPRÉSTIMOS E LINHAS DE CRÉDITO ──────────────────────────────

CREATE TABLE IF NOT EXISTS public.credit_facilities (
  id             UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      UUID          NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  name           TEXT          NOT NULL,
  type           TEXT          NOT NULL
                               CHECK (type IN ('loan', 'credit_line', 'overdraft', 'antecipacao_recebiveis')),
  bank           TEXT,
  total_amount   NUMERIC(15,2) NOT NULL,
  used_amount    NUMERIC(15,2) NOT NULL DEFAULT 0,
  interest_rate  NUMERIC(8,4),
  interest_type  TEXT          NOT NULL DEFAULT 'pre' CHECK (interest_type IN ('pre', 'pos')),
  start_date     DATE,
  end_date       DATE,
  status         TEXT          NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paid', 'suspended')),
  notes          TEXT,
  created_at     TIMESTAMPTZ   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.loan_installments (
  id                  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID          NOT NULL,
  credit_facility_id  UUID          NOT NULL REFERENCES public.credit_facilities(id) ON DELETE CASCADE,
  installment_number  INT           NOT NULL,
  due_date            DATE          NOT NULL,
  principal           NUMERIC(15,2),
  interest            NUMERIC(15,2),
  total               NUMERIC(15,2) NOT NULL,
  paid_date           DATE,
  status              TEXT          NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'paid', 'overdue')),
  transaction_id      UUID          REFERENCES public.transactions(id),
  created_at          TIMESTAMPTZ   DEFAULT NOW()
);

-- ─── CARTÕES CORPORATIVOS ──────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.corporate_cards (
  id             UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      UUID          NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  name           TEXT          NOT NULL,
  holder_name    TEXT,
  last_digits    CHAR(4),
  brand          TEXT          CHECK (brand IN ('visa', 'mastercard', 'elo', 'amex')),
  bank           TEXT,
  credit_limit   NUMERIC(15,2),
  closing_day    INT           CHECK (closing_day BETWEEN 1 AND 31),
  due_day        INT           CHECK (due_day BETWEEN 1 AND 31),
  cost_center_id UUID          REFERENCES public.cost_centers(id),
  status         TEXT          NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'blocked', 'cancelled')),
  created_at     TIMESTAMPTZ   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.card_statements (
  id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID          NOT NULL,
  card_id         UUID          NOT NULL REFERENCES public.corporate_cards(id) ON DELETE CASCADE,
  reference_month DATE          NOT NULL,
  closing_date    DATE          NOT NULL,
  due_date        DATE          NOT NULL,
  total_amount    NUMERIC(15,2) NOT NULL DEFAULT 0,
  paid_amount     NUMERIC(15,2) NOT NULL DEFAULT 0,
  status          TEXT          NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed', 'paid')),
  created_at      TIMESTAMPTZ   DEFAULT NOW()
);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

ALTER TABLE public.cost_centers             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transaction_cost_centers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bank_accounts            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payables_receivables     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.collection_rules         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reconciliation_matches   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.credit_facilities        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.loan_installments        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.corporate_cards          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.card_statements          ENABLE ROW LEVEL SECURITY;

-- Políticas de leitura
CREATE POLICY "rls_cost_centers"             ON public.cost_centers             USING (tenant_id = public.meu_tenant_id());
CREATE POLICY "rls_tcc"                      ON public.transaction_cost_centers USING (tenant_id = public.meu_tenant_id());
CREATE POLICY "rls_bank_accounts"            ON public.bank_accounts            USING (tenant_id = public.meu_tenant_id());
CREATE POLICY "rls_payables_receivables"     ON public.payables_receivables     USING (tenant_id = public.meu_tenant_id());
CREATE POLICY "rls_collection_rules"         ON public.collection_rules         USING (tenant_id = public.meu_tenant_id());
CREATE POLICY "rls_reconciliation_matches"   ON public.reconciliation_matches   USING (tenant_id = public.meu_tenant_id());
CREATE POLICY "rls_credit_facilities"        ON public.credit_facilities        USING (tenant_id = public.meu_tenant_id());
CREATE POLICY "rls_loan_installments"        ON public.loan_installments        USING (tenant_id = public.meu_tenant_id());
CREATE POLICY "rls_corporate_cards"          ON public.corporate_cards          USING (tenant_id = public.meu_tenant_id());
CREATE POLICY "rls_card_statements"          ON public.card_statements          USING (tenant_id = public.meu_tenant_id());

-- Políticas de escrita
CREATE POLICY "write_cost_centers"           ON public.cost_centers             FOR INSERT WITH CHECK (tenant_id = public.meu_tenant_id());
CREATE POLICY "update_cost_centers"          ON public.cost_centers             FOR UPDATE USING (tenant_id = public.meu_tenant_id());
CREATE POLICY "delete_cost_centers"          ON public.cost_centers             FOR DELETE USING (tenant_id = public.meu_tenant_id());

CREATE POLICY "write_tcc"                    ON public.transaction_cost_centers FOR INSERT WITH CHECK (tenant_id = public.meu_tenant_id());
CREATE POLICY "delete_tcc"                   ON public.transaction_cost_centers FOR DELETE USING (tenant_id = public.meu_tenant_id());

CREATE POLICY "write_bank_accounts"          ON public.bank_accounts            FOR INSERT WITH CHECK (tenant_id = public.meu_tenant_id());
CREATE POLICY "update_bank_accounts"         ON public.bank_accounts            FOR UPDATE USING (tenant_id = public.meu_tenant_id());

CREATE POLICY "write_payables_receivables"   ON public.payables_receivables     FOR INSERT WITH CHECK (tenant_id = public.meu_tenant_id());
CREATE POLICY "update_payables_receivables"  ON public.payables_receivables     FOR UPDATE USING (tenant_id = public.meu_tenant_id());
CREATE POLICY "delete_payables_receivables"  ON public.payables_receivables     FOR DELETE USING (tenant_id = public.meu_tenant_id());

CREATE POLICY "write_credit_facilities"      ON public.credit_facilities        FOR INSERT WITH CHECK (tenant_id = public.meu_tenant_id());
CREATE POLICY "update_credit_facilities"     ON public.credit_facilities        FOR UPDATE USING (tenant_id = public.meu_tenant_id());

CREATE POLICY "write_loan_installments"      ON public.loan_installments        FOR INSERT WITH CHECK (tenant_id = public.meu_tenant_id());
CREATE POLICY "update_loan_installments"     ON public.loan_installments        FOR UPDATE USING (tenant_id = public.meu_tenant_id());

CREATE POLICY "write_corporate_cards"        ON public.corporate_cards          FOR INSERT WITH CHECK (tenant_id = public.meu_tenant_id());
CREATE POLICY "update_corporate_cards"       ON public.corporate_cards          FOR UPDATE USING (tenant_id = public.meu_tenant_id());
