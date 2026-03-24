# FinPME – Makefile de desenvolvimento local
# Uso: make <target>

.PHONY: help install dev dev-backend dev-frontend \
        db-start db-stop db-reset db-studio db-status \
        redis-start redis-stop logs clean

# Garante que ~/.local/bin esteja no PATH (onde o Supabase CLI foi instalado)
export PATH := $(HOME)/.local/bin:$(PATH)

# Diretório do backend
BACKEND_DIR := backend
VENV        := $(BACKEND_DIR)/venv
PYTHON      := $(VENV)/bin/python
PIP         := $(VENV)/bin/pip
UVICORN     := $(VENV)/bin/uvicorn

##@ Ajuda
help: ## Mostra esta mensagem
	@awk 'BEGIN {FS = ":.*##"; printf "\nUso: make \033[36m<target>\033[0m\n"} \
	  /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } \
	  /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)

##@ Instalação
install: ## Instala dependências Python e copia arquivos de configuração
	@echo "→ Criando ambiente virtual Python..."
	python3.12 -m venv $(VENV)
	@echo "→ Instalando dependências..."
	$(PIP) install --upgrade pip
	$(PIP) install -r $(BACKEND_DIR)/requirements.txt
	@echo "→ Configurando arquivos de ambiente..."
	@if [ ! -f $(BACKEND_DIR)/.env.local ]; then \
		cp $(BACKEND_DIR)/.env.local $(BACKEND_DIR)/.env.local; \
		echo "  ✓ backend/.env.local já existe"; \
	else \
		echo "  ✓ backend/.env.local já existe"; \
	fi
	@if [ ! -f frontend/env.js ]; then \
		cp frontend/env.example.js frontend/env.js; \
		echo "  ✓ frontend/env.js criado a partir de env.example.js"; \
	else \
		echo "  ✓ frontend/env.js já existe"; \
	fi
	@echo ""
	@echo "✅ Instalação concluída."
	@echo "   Edite backend/.env.local e adicione sua ANTHROPIC_API_KEY."
	@echo "   Depois rode: make db-start"

##@ Banco de dados (Supabase CLI)
db-start: ## Inicia o Supabase local (PostgreSQL + Auth + Storage + Studio)
	@echo "→ Iniciando Supabase local..."
	supabase start
	@echo ""
	@echo "→ Aplicando migrations..."
	supabase db reset
	@echo ""
	@echo "✅ Supabase pronto. Studio em: http://localhost:54323"

db-stop: ## Para o Supabase local
	supabase stop

db-reset: ## Reseta o banco e reaaplica migrations + seed
	@echo "→ Resetando banco de dados..."
	supabase db reset
	@echo "✅ Banco resetado."

db-studio: ## Abre o Supabase Studio no browser
	@open http://localhost:54323 2>/dev/null || xdg-open http://localhost:54323

db-status: ## Mostra URLs e chaves do Supabase local
	supabase status

##@ Redis
redis-start: ## Inicia o Redis local via Docker Compose
	@echo "→ Iniciando Redis..."
	docker compose up -d redis
	@echo "✅ Redis rodando em localhost:6379"

redis-stop: ## Para o Redis
	docker compose stop redis

##@ Desenvolvimento
dev-backend: ## Inicia o backend FastAPI com hot-reload
	@echo "→ Iniciando backend em http://localhost:8000"
	@echo "   Docs: http://localhost:8000/docs"
	cd $(BACKEND_DIR) && \
	  ENV_FILE=.env.local \
	  $(UVICORN) main:app --reload --host 0.0.0.0 --port 8000 \
	  --env-file .env.local

dev-frontend: ## Serve o frontend estático em http://localhost:4000
	@echo "→ Iniciando frontend em http://localhost:4000"
	@if command -v npx >/dev/null 2>&1; then \
		npx serve -s frontend -l 4000; \
	else \
		echo "  npx não encontrado. Usando Python http.server (sem SPA fallback)..."; \
		cd frontend && python3 -m http.server 4000; \
	fi

dev: ## Inicia backend + frontend em paralelo (requer tmux ou usa background)
	@echo "→ Iniciando ambiente de desenvolvimento completo..."
	@echo "   Backend : http://localhost:8000"
	@echo "   Frontend: http://localhost:4000"
	@echo "   Docs API: http://localhost:8000/docs"
	@echo ""
	@if command -v tmux >/dev/null 2>&1; then \
		tmux new-session -d -s finpme -n backend \
		  "cd $(BACKEND_DIR) && $(UVICORN) main:app --reload --host 0.0.0.0 --port 8000 --env-file .env.local; read" \; \
		new-window -t finpme -n frontend \
		  "npx serve -s frontend -l 4000 2>/dev/null || cd frontend && python3 -m http.server 4000; read" \; \
		attach-session -t finpme; \
	else \
		echo "tmux não encontrado. Iniciando backend em background e frontend no foreground..."; \
		cd $(BACKEND_DIR) && $(UVICORN) main:app --reload --host 0.0.0.0 --port 8000 --env-file .env.local & \
		sleep 2 && \
		(npx serve -s frontend -l 4000 2>/dev/null || cd frontend && python3 -m http.server 4000); \
	fi

##@ Utilitários
logs: ## Mostra logs do Docker Compose (Redis)
	docker compose logs -f

clean: ## Remove ambiente virtual e cache Python
	rm -rf $(VENV)
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Ambiente limpo."
