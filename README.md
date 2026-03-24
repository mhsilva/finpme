# FinPME

Plataforma SaaS de inteligência financeira para PMEs brasileiras. Processa extratos bancários (OFX, CSV) e NF-e XML, categoriza transações com IA e gera DRE e fluxo de caixa automaticamente.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Banco / Auth / Storage | Supabase (PostgreSQL + GoTrue + Storage) |
| IA | Anthropic Claude (`claude-sonnet-4-20250514`) |
| Cache | Redis (local) / Upstash (produção) |
| Frontend | HTML + Preact via CDN + Tailwind via CDN |
| Deploy backend | Railway (Dockerfile incluído) |
| Deploy frontend | Cloudflare Pages |

---

## Desenvolvimento Local

### Pré-requisitos

| Ferramenta | Versão mínima | Como instalar |
|---|---|---|
| **Docker Desktop** | 4.x | https://docker.com/products/docker-desktop |
| **Supabase CLI** | 1.x | `brew install supabase/tap/supabase` |
| **Python** | 3.12 | `brew install python@3.12` |
| **Node.js** | 18+ (opcional, para `npx serve`) | https://nodejs.org |

> **macOS com Homebrew:** `brew install supabase/tap/supabase python@3.12`

---

### 1. Clonar e instalar

```bash
git clone <url-do-repo>
cd finpme

# Instala dependências Python e cria arquivos de configuração
make install
```

Isso cria:
- `backend/venv/` — ambiente virtual Python
- `frontend/env.js` — configuração do frontend (copiado de `env.example.js`)

---

### 2. Iniciar o Supabase local

```bash
make db-start
```

Isso executa:
1. `supabase start` — sobe containers Docker com PostgreSQL, GoTrue (auth), Storage, Studio
2. `supabase db reset` — aplica as migrations de `supabase/migrations/` e o `supabase/seed.sql`

Ao final você verá algo como:

```
API URL:    http://127.0.0.1:54321
DB URL:     postgresql://postgres:postgres@127.0.0.1:54322/postgres
Studio:     http://127.0.0.1:54323
JWT Secret: super-secret-jwt-token-with-at-least-32-characters-long
anon key:   eyJhbGci...
service_role key: eyJhbGci...
```

> **Importante:** os valores padrão já estão pré-preenchidos em `backend/.env.local` e `frontend/env.js`. Se por algum motivo divergirem, rode `make db-status` e copie os valores corretos.

---

### 3. Iniciar o Redis local

```bash
make redis-start
```

Sobe um container Redis na porta `6379` via Docker Compose.

---

### 4. Configurar a chave da Anthropic

Edite `backend/.env.local` e preencha a única variável que não tem valor padrão:

```env
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
```

Obtenha sua chave em https://console.anthropic.com.

---

### 5. Rodar o ambiente completo

```bash
# Opção A — janelas separadas com tmux (recomendado)
make dev

# Opção B — dois terminais separados
make dev-backend    # terminal 1
make dev-frontend   # terminal 2
```

| Serviço | URL |
|---|---|
| Frontend | http://localhost:4000 |
| Backend API | http://localhost:8000 |
| Docs interativos (Swagger) | http://localhost:8000/docs |
| Supabase Studio | http://localhost:54323 |
| Inbucket (e-mails locais) | http://localhost:54324 |

---

### 6. Criar o primeiro usuário

Acesse http://localhost:4000, clique em **Criar conta** e preencha os dados. Como `enable_confirmations = false` está configurado no `supabase/config.toml`, o e-mail é confirmado automaticamente em desenvolvimento.

> **Dica:** os e-mails enviados pelo Supabase local (confirmações, reset de senha) ficam disponíveis em http://localhost:54324 (Inbucket), sem precisar de SMTP real.

---

### Fluxo de trabalho típico

```
1. make db-start        # uma vez por sessão (ou depois de reiniciar o Mac)
2. make redis-start     # uma vez por sessão
3. make dev             # abre backend + frontend
4. Acesse http://localhost:4000
5. Faça upload de um extrato OFX/CSV
6. Veja os lançamentos categorizados em "Transações"
7. Consulte o DRE em "Relatórios"
```

---

### Referência de comandos

```bash
make help           # lista todos os comandos disponíveis

make db-start       # inicia Supabase + aplica migrations
make db-stop        # para o Supabase
make db-reset       # reseta banco e reaaplica migrations + seed
make db-studio      # abre o Studio no browser
make db-status      # mostra URLs e chaves do Supabase local

make redis-start    # inicia Redis via Docker
make redis-stop     # para o Redis

make dev            # backend + frontend (usa tmux se disponível)
make dev-backend    # só o backend FastAPI (porta 8000)
make dev-frontend   # só o frontend estático (porta 4000)

make install        # instala dependências e cria arquivos de config
make clean          # remove venv e cache Python
```

---

### Estrutura de arquivos de configuração

```
finpme/
├── backend/
│   ├── .env.local        # ← vars para dev local (gitignored)
│   └── .env.example      # ← template para produção
├── frontend/
│   ├── env.js            # ← config do frontend para dev local (gitignored)
│   └── env.example.js    # ← template para produção
└── supabase/
    └── config.toml       # ← configuração do Supabase CLI local
```

---

## Deploy em Produção

### Backend — Railway

1. Crie um projeto no [Railway](https://railway.app) e conecte o repositório
2. Configure o **root directory** como `backend`
3. O Railway detecta o `Dockerfile` automaticamente
4. Adicione as variáveis de ambiente do `backend/.env.example` com valores de produção

### Frontend — Cloudflare Pages

1. Crie um projeto em [Cloudflare Pages](https://pages.cloudflare.com) conectado ao repositório
2. **Build settings:**
   - Root directory: `frontend`
   - Build command: *(deixe vazio — não tem build step)*
   - Output directory: `/`
3. Adicione as variáveis de ambiente do Cloudflare Pages (ou use uma Pages Function para injetar `window.__ENV__` dinamicamente)

### Banco — Supabase Cloud

1. Crie um projeto em [supabase.com](https://supabase.com)
2. Execute as migrations: SQL Editor → cole `supabase/migrations/001_initial.sql`
3. Execute o seed: SQL Editor → cole `supabase/seed.sql`
4. Crie o bucket de Storage chamado **`extratos`** (privado)
5. Ative Google OAuth em **Authentication → Providers → Google**

---

## Arquitetura

```
Browser
  └─▶ Cloudflare Pages (HTML + Preact + Tailwind)
         └─▶ FastAPI (Railway / Fly.io)
                ├─▶ Supabase (PostgreSQL + Auth + Storage)
                ├─▶ Redis (Upstash / local)
                └─▶ Anthropic Claude API
```

Todas as tabelas têm `tenant_id` + **Row Level Security** no Supabase, garantindo isolamento total entre empresas.

---

## Variáveis de Ambiente

### Backend (`backend/.env.local` / Railway)

| Variável | Descrição |
|---|---|
| `SUPABASE_URL` | URL do projeto Supabase |
| `SUPABASE_SERVICE_KEY` | Chave `service_role` (nunca expor no frontend) |
| `SUPABASE_JWT_SECRET` | Segredo JWT para validar tokens |
| `ANTHROPIC_API_KEY` | Chave da API Anthropic |
| `UPSTASH_REDIS_URL` | `redis://localhost:6379` (local) ou URL Upstash (prod) |
| `UPSTASH_REDIS_TOKEN` | Token Upstash (deixe vazio para dev local) |

### Frontend (`frontend/env.js` / Cloudflare Pages)

| Variável | Descrição |
|---|---|
| `SUPABASE_URL` | URL do projeto Supabase (mesma do backend) |
| `SUPABASE_ANON_KEY` | Chave `anon` (segura para expor) |
| `API_URL` | URL do backend FastAPI |
