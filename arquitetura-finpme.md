# FinPME – Arquitetura da Plataforma

## Visão Geral

Plataforma SaaS multitenant de inteligência financeira para PMEs. O usuário faz upload de extratos/NFs, a IA categoriza, e a plataforma gera DRE, fluxo de caixa e análises automaticamente.

---

## Stack Tecnológico

| Camada | Tecnologia | Justificativa |
|---|---|---|
| Frontend | Cloudflare Pages (estático) + Vanilla JS ou Preact | Compatível com Workers, sem SSR |
| Backend API | Python + FastAPI | Rápido, async, ótimo ecossistema de dados |
| Banco de dados | Supabase (PostgreSQL) | Auth nativo, RLS multitenant, storage de arquivos |
| Auth | Supabase Auth | Google OAuth + email/senha out of the box |
| IA / LLM | Anthropic API (Claude) | Categorização, geração de relatórios, análises |
| Storage de arquivos | Supabase Storage | Upload de extratos OFX, XML NF-e, PDFs |
| Deploy Backend | Railway ou Fly.io | Python com FastAPI não roda em Workers |
| Cache/Filas | Upstash Redis (serverless) | Fila de processamento de arquivos, rate limiting |

---

## Diagrama de Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                    USUÁRIO (Browser)                     │
└────────────────────────┬────────────────────────────────┘
                         │ HTTPS
┌────────────────────────▼────────────────────────────────┐
│           Cloudflare Pages (Frontend Estático)           │
│   HTML + JS (Preact/Vanilla) · Tailwind CSS              │
│   – Login/Cadastro    – Dashboard                        │
│   – Upload extratos   – Visualização DRE/Caixa           │
└────────────────────────┬────────────────────────────────┘
                         │ REST / JSON
┌────────────────────────▼────────────────────────────────┐
│              FastAPI (Python) – Backend API              │
│                   Railway / Fly.io                       │
│                                                          │
│  /auth/*          → proxy Supabase Auth                  │
│  /upload          → recebe arquivo, salva no Storage     │
│  /process/{id}    → dispara pipeline de processamento    │
│  /reports/*       → DRE, Fluxo de Caixa, Balanço        │
│  /transactions/*  → CRUD de lançamentos                  │
│  /ai/chat         → chat financeiro livre                │
└──────┬──────────────────────┬───────────────────────────┘
       │                      │
┌──────▼──────┐    ┌──────────▼──────────────────────────┐
│   Upstash   │    │         Supabase                     │
│   Redis     │    │                                      │
│             │    │  Auth (Google OAuth + email/senha)   │
│  job queue  │    │  PostgreSQL (dados estruturados)     │
│  rate limit │    │  Storage (arquivos brutos)           │
│  cache DRE  │    │  RLS (isolamento multitenant)        │
└──────┬──────┘    └──────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────┐
│              Pipeline de Processamento (Worker)          │
│                    Python background task                │
│                                                          │
│  1. Ler arquivo (OFX / XML NF-e / CSV / PDF)            │
│  2. Parsear transações brutas                            │
│  3. Enviar para Claude API → categorização               │
│  4. Salvar lançamentos categorizados no Postgres         │
│  5. Gerar DRE + Fluxo de Caixa                          │
│  6. Notificar frontend (polling ou Supabase Realtime)    │
└──────────────────────────────────────────────────────────┘
```

---

## Modelo de Dados (PostgreSQL / Supabase)

### Multitenant via `tenant_id`

Todas as tabelas têm `tenant_id` com Row Level Security (RLS) no Supabase, garantindo isolamento total entre empresas.

```sql
-- Tenants (empresas)
CREATE TABLE tenants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  cnpj TEXT,
  tax_regime TEXT, -- simples, presumido, real
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Usuários ligados a tenants
CREATE TABLE tenant_users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES tenants(id),
  user_id UUID REFERENCES auth.users(id), -- Supabase Auth
  role TEXT DEFAULT 'owner', -- owner, admin, viewer
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Transações financeiras (coração do sistema)
CREATE TABLE transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES tenants(id),
  date DATE NOT NULL,
  description TEXT NOT NULL,
  amount NUMERIC(15,2) NOT NULL, -- positivo = entrada, negativo = saída
  category TEXT, -- ex: "Despesas Administrativas > Aluguel"
  subcategory TEXT,
  dre_line TEXT, -- mapeamento direto para linha do DRE
  source TEXT, -- 'ofx', 'nfe_xml', 'manual', 'csv'
  source_file_id UUID, -- referência ao arquivo original
  ai_categorized BOOLEAN DEFAULT FALSE,
  ai_confidence NUMERIC(3,2), -- 0.0 a 1.0
  confirmed BOOLEAN DEFAULT FALSE, -- usuário confirmou/editou
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Arquivos enviados
CREATE TABLE uploaded_files (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES tenants(id),
  filename TEXT,
  file_type TEXT, -- 'ofx', 'xml', 'csv', 'pdf'
  storage_path TEXT, -- caminho no Supabase Storage
  status TEXT DEFAULT 'pending', -- pending, processing, done, error
  processed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Cache de relatórios gerados
CREATE TABLE reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES tenants(id),
  report_type TEXT, -- 'dre', 'cash_flow', 'balance'
  period_start DATE,
  period_end DATE,
  data JSONB, -- relatório completo em JSON
  generated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Plano de contas customizável por tenant
CREATE TABLE chart_of_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES tenants(id),
  code TEXT,
  name TEXT,
  parent_id UUID REFERENCES chart_of_accounts(id),
  dre_line TEXT,
  type TEXT -- 'revenue', 'cost', 'expense', 'asset', 'liability'
);
```

---

## Fluxo de Autenticação (Supabase Auth)

```
1. Usuário clica "Entrar com Google" ou preenche email/senha
2. Supabase Auth gerencia OAuth e sessão (JWT)
3. Frontend armazena o JWT no localStorage
4. Toda requisição ao FastAPI envia o JWT no header Authorization
5. FastAPI valida o JWT com a chave pública do Supabase
6. Extrai user_id → busca tenant_id do usuário → aplica RLS
```

### Onboarding (novo usuário)
```
Cadastro → Cria conta no Supabase Auth
         → Cria tenant (empresa)
         → Cria tenant_user (owner)
         → Redireciona para setup inicial (nome empresa, CNPJ, regime fiscal)
```

---

## Pipeline de Processamento de Arquivos

```python
# Fluxo resumido
async def process_file(file_id: str, tenant_id: str):

    # 1. Baixa arquivo do Supabase Storage
    file = await storage.download(file_id)

    # 2. Parse conforme tipo
    if file.type == "ofx":
        transactions = parse_ofx(file)
    elif file.type == "xml":
        transactions = parse_nfe_xml(file)
    elif file.type == "csv":
        transactions = parse_csv(file)

    # 3. Envia lote para Claude API categorizar
    categories = await claude_categorize(transactions, tenant_id)

    # 4. Salva no banco
    await save_transactions(transactions, categories, tenant_id)

    # 5. Invalida cache de relatórios do período
    await redis.delete(f"report:{tenant_id}:*")

    # 6. Atualiza status do arquivo
    await update_file_status(file_id, "done")
```

### Prompt de categorização (Claude)
```
Você é um assistente contábil especializado em PMEs brasileiras.
Analise as transações abaixo e categorize cada uma conforme o plano de contas.

Regime fiscal da empresa: {regime}
Plano de contas: {chart_of_accounts}

Transações:
{transactions_json}

Responda SOMENTE em JSON no formato:
[{"id": "...", "category": "...", "subcategory": "...", "dre_line": "...", "confidence": 0.95}]
```

---

## Geração do DRE

O DRE é gerado dinamicamente a partir dos lançamentos categorizados:

```python
def generate_dre(tenant_id, period_start, period_end):
    transactions = db.query("""
        SELECT dre_line, SUM(amount) as total
        FROM transactions
        WHERE tenant_id = %s
          AND date BETWEEN %s AND %s
          AND confirmed = TRUE OR ai_confidence > 0.85
        GROUP BY dre_line
    """, [tenant_id, period_start, period_end])

    return {
        "receita_bruta": ...,
        "deducoes": ...,
        "receita_liquida": ...,
        "cmv": ...,
        "lucro_bruto": ...,
        "despesas_operacionais": {...},
        "ebitda": ...,
        "lucro_liquido": ...
    }
```

---

## Estrutura de Pastas do Projeto

```
finpme/
├── backend/
│   ├── main.py                 # FastAPI app
│   ├── routers/
│   │   ├── auth.py
│   │   ├── upload.py
│   │   ├── transactions.py
│   │   ├── reports.py
│   │   └── ai.py
│   ├── services/
│   │   ├── parsers/
│   │   │   ├── ofx_parser.py
│   │   │   ├── nfe_parser.py
│   │   │   └── csv_parser.py
│   │   ├── categorizer.py      # integração Claude API
│   │   ├── dre_generator.py
│   │   └── cashflow_generator.py
│   ├── models/
│   │   └── schemas.py          # Pydantic models
│   ├── db/
│   │   └── supabase.py         # cliente Supabase
│   └── requirements.txt
│
├── frontend/
│   ├── index.html              # SPA entry point
│   ├── src/
│   │   ├── pages/
│   │   │   ├── login.js
│   │   │   ├── dashboard.js
│   │   │   ├── upload.js
│   │   │   ├── transactions.js
│   │   │   └── reports.js
│   │   ├── components/
│   │   │   ├── dre-chart.js
│   │   │   ├── cashflow-chart.js
│   │   │   └── transaction-table.js
│   │   └── lib/
│   │       ├── api.js          # cliente HTTP
│   │       └── auth.js         # Supabase Auth client
│   └── _routes.json            # Cloudflare Pages config
│
└── supabase/
    ├── migrations/
    │   └── 001_initial.sql     # Schema + RLS policies
    └── seed.sql                # Plano de contas padrão
```

---

## Roadmap de Desenvolvimento

### MVP (4–6 semanas)
- [ ] Auth (Google OAuth + email/senha)
- [ ] Upload de extrato OFX/CSV
- [ ] Categorização por IA (Claude)
- [ ] Tela de revisão de lançamentos
- [ ] Geração de DRE

### Fase 2
- [ ] Leitura de XML NF-e
- [ ] Fluxo de caixa projetado
- [ ] Contas a pagar/receber
- [ ] Alertas de saúde financeira
- [ ] Multi-usuário por empresa

### Fase 3
- [ ] Chat financeiro livre ("quanto gastei com marketing em março?")
- [ ] Benchmark por setor
- [ ] Exportação para contador (PDF, Excel)
- [ ] Integração Open Finance

---

## Variáveis de Ambiente

```env
# Backend
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=xxx          # chave service_role (só no backend)
SUPABASE_JWT_SECRET=xxx           # para validar tokens do frontend
ANTHROPIC_API_KEY=sk-ant-xxx
UPSTASH_REDIS_URL=xxx
UPSTASH_REDIS_TOKEN=xxx

# Frontend (público)
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=xxx        # chave anon (segura para expor)
VITE_API_URL=https://api.finpme.com
```
