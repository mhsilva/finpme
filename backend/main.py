"""
FinPME – Backend API
Plataforma de inteligência financeira para PMEs brasileiras.
"""

import logging
import os
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers import ai, auth, reports, transactions, upload

load_dotenv()

# ---------------------------------------------------------------------------
# Configuração de logs
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Instância FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(
    title="FinPME API",
    description="API de inteligência financeira para PMEs brasileiras",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# CORS
# Em produção, restringe ao domínio do frontend via FRONTEND_URL.
# Para dev local, define FRONTEND_URL=* no .env.local.
# ---------------------------------------------------------------------------
_frontend_url = os.environ.get("FRONTEND_URL", "*")
_allow_origins = ["*"] if _frontend_url == "*" else [_frontend_url.rstrip("/")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=_frontend_url != "*",
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Middleware de autenticação
# Valida o JWT do Supabase e injeta user_id + tenant_id no request state.
# Rotas públicas (prefixadas com /auth) não passam por aqui.
# ---------------------------------------------------------------------------
ROTAS_PUBLICAS = {"/", "/docs", "/openapi.json", "/redoc"}
PREFIXOS_PUBLICOS = ("/auth/",)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")


@app.middleware("http")
async def autenticar_requisicao(request: Request, call_next):
    """Valida JWT do Supabase em todas as rotas protegidas."""
    caminho = request.url.path

    # Libera rotas públicas sem autenticação
    if caminho in ROTAS_PUBLICAS or any(caminho.startswith(p) for p in PREFIXOS_PUBLICOS):
        return await call_next(request)

    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Token de autenticação ausente ou inválido"},
        )

    token = authorization.removeprefix("Bearer ").strip()

    try:
        # Valida o token junto ao Supabase e obtém o usuário
        async with httpx.AsyncClient(timeout=10) as client:
            resposta = await client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": os.environ.get("SUPABASE_SERVICE_KEY", ""),
                },
            )

        if resposta.status_code != 200:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Token inválido ou expirado"},
            )

        dados_usuario = resposta.json()
        user_id: str = dados_usuario["id"]

        # Busca tenant do usuário
        from db.supabase import get_tenant_id
        tenant_id: Optional[str] = get_tenant_id(user_id)

        # Injeta no estado da requisição
        request.state.user_id = user_id
        request.state.tenant_id = tenant_id
        request.state.user_data = dados_usuario

    except Exception as e:
        logger.error(f"Erro ao validar token: {e}")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Erro ao validar autenticação"},
        )

    return await call_next(request)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth.router, prefix="/auth", tags=["Autenticação"])
app.include_router(upload.router, prefix="/upload", tags=["Upload de Arquivos"])
app.include_router(transactions.router, prefix="/transactions", tags=["Transações"])
app.include_router(reports.router, prefix="/reports", tags=["Relatórios"])
app.include_router(ai.router, prefix="/ai", tags=["Inteligência Artificial"])


# ---------------------------------------------------------------------------
# Rota raiz
# ---------------------------------------------------------------------------
@app.get("/")
async def raiz():
    return {"status": "ok", "servico": "FinPME API", "versao": "0.1.0"}
