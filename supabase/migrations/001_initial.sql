-- ============================================================
-- FinPME – Migration inicial
-- Cria schema completo com RLS para isolamento multitenant
-- ============================================================

-- Habilita extensão para UUID
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- TABELAS
-- ============================================================

-- Empresas (tenants)
CREATE TABLE IF NOT EXISTS public.tenants (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT        NOT NULL,
  cnpj        TEXT,
  tax_regime  TEXT        DEFAULT 'simples' CHECK (tax_regime IN ('simples', 'presumido', 'real')),
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Usuários vinculados a tenants
CREATE TABLE IF NOT EXISTS public.tenant_users (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   UUID        NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  user_id     UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role        TEXT        NOT NULL DEFAULT 'owner' CHECK (role IN ('owner', 'admin', 'viewer')),
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (tenant_id, user_id)
);

-- Transações financeiras (coração do sistema)
CREATE TABLE IF NOT EXISTS public.transactions (
  id              UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID           NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  date            DATE           NOT NULL,
  description     TEXT           NOT NULL,
  amount          NUMERIC(15,2)  NOT NULL,  -- positivo = entrada, negativo = saída
  category        TEXT,
  subcategory     TEXT,
  dre_line        TEXT,          -- receita_bruta | deducoes | cmv | despesa_vendas | despesa_admin | despesa_financeira | outros
  source          TEXT,          -- ofx | nfe_xml | manual | csv
  source_file_id  UUID,
  ai_categorized  BOOLEAN        DEFAULT FALSE,
  ai_confidence   NUMERIC(4,3),  -- 0.000 a 1.000
  confirmed       BOOLEAN        DEFAULT FALSE,
  created_at      TIMESTAMPTZ    DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transactions_tenant_date ON public.transactions (tenant_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_dre_line    ON public.transactions (tenant_id, dre_line);

-- Arquivos enviados pelos usuários
CREATE TABLE IF NOT EXISTS public.uploaded_files (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID        NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  filename      TEXT,
  file_type     TEXT        CHECK (file_type IN ('ofx', 'xml', 'csv', 'pdf')),
  storage_path  TEXT,
  status        TEXT        NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'processing', 'done', 'error')),
  processed_at  TIMESTAMPTZ,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Cache de relatórios gerados
CREATE TABLE IF NOT EXISTS public.reports (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID        NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  report_type   TEXT        NOT NULL CHECK (report_type IN ('dre', 'cash_flow', 'balance')),
  period_start  DATE        NOT NULL,
  period_end    DATE        NOT NULL,
  data          JSONB       NOT NULL DEFAULT '{}',
  generated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Plano de contas customizável por tenant
CREATE TABLE IF NOT EXISTS public.chart_of_accounts (
  id          UUID  PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   UUID  REFERENCES public.tenants(id) ON DELETE CASCADE,  -- NULL = plano padrão global
  code        TEXT,
  name        TEXT  NOT NULL,
  parent_id   UUID  REFERENCES public.chart_of_accounts(id),
  dre_line    TEXT  CHECK (dre_line IN ('receita_bruta','deducoes','cmv','despesa_vendas','despesa_admin','despesa_financeira','outros')),
  type        TEXT  NOT NULL CHECK (type IN ('revenue','cost','expense','asset','liability'))
);

CREATE INDEX IF NOT EXISTS idx_chart_tenant ON public.chart_of_accounts (tenant_id);

-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- Garante isolamento total entre tenants
-- ============================================================

ALTER TABLE public.tenants          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenant_users     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.uploaded_files   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reports          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chart_of_accounts ENABLE ROW LEVEL SECURITY;

-- Função auxiliar: retorna o tenant_id do usuário autenticado
CREATE OR REPLACE FUNCTION public.meu_tenant_id()
RETURNS UUID
LANGUAGE SQL
STABLE
AS $$
  SELECT tenant_id
  FROM public.tenant_users
  WHERE user_id = auth.uid()
  LIMIT 1;
$$;

-- Políticas: usuário só acessa dados do seu próprio tenant

CREATE POLICY "tenant_isolation_tenants"
  ON public.tenants
  USING (id = public.meu_tenant_id());

CREATE POLICY "tenant_isolation_tenant_users"
  ON public.tenant_users
  USING (tenant_id = public.meu_tenant_id());

CREATE POLICY "tenant_isolation_transactions"
  ON public.transactions
  USING (tenant_id = public.meu_tenant_id());

CREATE POLICY "tenant_isolation_uploaded_files"
  ON public.uploaded_files
  USING (tenant_id = public.meu_tenant_id());

CREATE POLICY "tenant_isolation_reports"
  ON public.reports
  USING (tenant_id = public.meu_tenant_id());

-- Plano de contas: acessa o próprio + os globais (tenant_id IS NULL)
CREATE POLICY "tenant_isolation_chart_of_accounts"
  ON public.chart_of_accounts
  USING (tenant_id = public.meu_tenant_id() OR tenant_id IS NULL);

-- Políticas de escrita: apenas owner/admin podem inserir e atualizar
CREATE POLICY "write_transactions"
  ON public.transactions FOR INSERT
  WITH CHECK (tenant_id = public.meu_tenant_id());

CREATE POLICY "update_transactions"
  ON public.transactions FOR UPDATE
  USING (tenant_id = public.meu_tenant_id());

CREATE POLICY "delete_transactions"
  ON public.transactions FOR DELETE
  USING (tenant_id = public.meu_tenant_id());

CREATE POLICY "write_uploaded_files"
  ON public.uploaded_files FOR INSERT
  WITH CHECK (tenant_id = public.meu_tenant_id());
