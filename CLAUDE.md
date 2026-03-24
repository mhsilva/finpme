# FinPME — Contexto para Claude Code

SaaS de inteligência financeira para PMEs brasileiras. Processa extratos (OFX, CSV) e NF-e XML, categoriza transações com IA e gera DRE e fluxo de caixa automaticamente.

## Stack

- **Backend**: FastAPI + Python 3.12, async, BackgroundTasks
- **Banco/Auth**: Supabase Cloud (PostgreSQL + GoTrue) com RLS multitenant via `tenant_id`
- **IA**: Anthropic Claude API — modelo: `claude-haiku-4-5-20251001`
- **Cache**: Upstash Redis (relatórios DRE e cashflow)
- **Frontend**: Preact via CDN + htm/preact + Tailwind CSS via CDN — **sem build step**
- **Deploy backend**: Railway (auto-deploy no push pro `main`)
- **Deploy frontend**: Cloudflare Pages (auto-deploy; `build.sh` gera `frontend/env.js` a partir de env vars)

## Infraestrutura de produção

- Supabase: `wuuenbfprjdwtdmkfzcx.supabase.co`
- Railway: `finpme-production.up.railway.app`
- Cloudflare Pages: `finpme.pages.dev`
- Redis: `bursting-mule-83685.upstash.io`
- Repo: `git@github.com:mhsilva/finpme.git`

## Regras importantes

- **Tailwind CDN**: `@apply` em `<style>` NÃO funciona. Sempre colocar classes Tailwind direto nos atributos `class` dos componentes.
- **Supabase keys**: usar as "legacy keys" (formato `eyJ...`), não as novas `sb_publishable_`.
- **CORS**: o middleware de auth em `main.py` deixa `OPTIONS` passar (preflight) — não remover essa condição.
- **Modelo Claude**: `claude-haiku-4-5-20251001` nos dois lugares: `routers/ai.py` e `services/categorizer.py`.
- **Secrets**: `.env.local` e `frontend/env.js` são gitignored — nunca commitar.

## Features implementadas

1. Upload de OFX, CSV e NF-e XML com processamento em background
2. Categorização automática de transações via Claude
3. DRE e Fluxo de Caixa com cache Redis
4. Edição inline de categorias + badge de confiança IA na tela de Lançamentos
5. Agente financeiro com Tool Use + streaming SSE (`/chat` no frontend, `POST /ai/agent` no backend)
6. Confirmação de pagamentos: botão ✓ na tabela + tools `listar_pendentes` e `confirmar_transacao` no agente

## Tools do agente (`backend/services/agent_tools.py`)

| Tool | Descrição |
|---|---|
| `gerar_dre` | Gera DRE para um período |
| `gerar_fluxo_caixa` | Gera fluxo de caixa semanal |
| `buscar_transacoes` | Busca transações com filtros |
| `resumo_periodo` | Overview financeiro rápido |
| `listar_pendentes` | Lista transações não confirmadas |
| `confirmar_transacao` | Confirma transações por ID |

## Arquivos-chave

```
backend/
  main.py                      # FastAPI app, CORS, middleware de auth
  routers/ai.py                # Agente com agentic loop + SSE streaming
  routers/reports.py           # DRE e cashflow com cache Redis
  routers/upload.py            # Upload + pipeline de processamento
  services/agent_tools.py      # Ferramentas do agente
  services/categorizer.py      # Categorização de transações via Claude
  services/dre_generator.py    # Gerador de DRE
  services/cashflow_generator.py
  services/parsers/            # OFX, NF-e XML, CSV
  models/schemas.py            # Pydantic models
  db/supabase.py               # Client Supabase

frontend/
  index.html                   # Entry point, importmap, Tailwind CDN
  src/app.js                   # SPA entry, roteador, sidebar
  src/pages/chat.js            # Página do agente (streaming SSE)
  src/pages/transactions.js    # Lançamentos com confirmação
  src/pages/dashboard.js
  src/pages/upload.js
  src/pages/reports.js
  src/lib/api.js               # Cliente HTTP + sendAgentMessage (SSE)
  src/lib/auth.js              # Supabase Auth wrapper

supabase/
  migrations/001_initial.sql   # Schema completo com RLS multitenant
  seed.sql                     # Plano de contas padrão
```

## Próximas features

- **Receitas e entradas**: gestão de receitas, entradas de caixa e faturamento
- **Upload via chat**: selecionar arquivo direto na tela do agente
