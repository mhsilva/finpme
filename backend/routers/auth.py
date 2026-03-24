"""
Router de autenticação.
Gerencia registro, login e dados do usuário autenticado.
"""

import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, Request, status

from db.supabase import create_tenant, create_tenant_user, get_supabase_client, get_tenant_id, get_tenant
from models.schemas import UserCreate, UserLogin, UserResponse, Tenant

logger = logging.getLogger(__name__)
router = APIRouter()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def registrar_usuario(dados: UserCreate):
    """
    Registra novo usuário:
    1. Cria conta no Supabase Auth
    2. Cria tenant (empresa)
    3. Vincula usuário ao tenant como 'owner'
    """
    client = get_supabase_client()

    # 1. Cria usuário no Supabase Auth
    try:
        resultado_auth = client.auth.admin.create_user({
            "email": dados.email,
            "password": dados.password,
            "email_confirm": True,
            "user_metadata": {"full_name": dados.full_name or ""},
        })
        user_id = resultado_auth.user.id
    except Exception as e:
        logger.error(f"Erro ao criar usuário no Supabase Auth: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao criar conta: {str(e)}",
        )

    # 2. Cria tenant
    try:
        tenant = create_tenant(
            name=dados.company_name,
            cnpj=dados.cnpj,
            tax_regime=dados.tax_regime or "simples",
        )
    except Exception as e:
        logger.error(f"Erro ao criar tenant: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao criar empresa",
        )

    # 3. Vincula usuário ao tenant
    try:
        create_tenant_user(tenant_id=tenant["id"], user_id=str(user_id), role="owner")
    except Exception as e:
        logger.error(f"Erro ao vincular usuário ao tenant: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao configurar empresa",
        )

    logger.info(f"Novo usuário registrado: {dados.email} → tenant {tenant['id']}")
    return {
        "message": "Conta criada com sucesso",
        "user_id": str(user_id),
        "tenant_id": tenant["id"],
    }


@router.post("/login")
async def login(dados: UserLogin):
    """
    Autentica o usuário via email/senha no Supabase Auth.
    Retorna o JWT de sessão.
    """
    async with httpx.AsyncClient(timeout=15) as client:
        resposta = await client.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            json={"email": dados.email, "password": dados.password},
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Content-Type": "application/json",
            },
        )

    if resposta.status_code != 200:
        detalhe = resposta.json().get("error_description", "Credenciais inválidas")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detalhe,
        )

    dados_sessao = resposta.json()
    logger.info(f"Login bem-sucedido: {dados.email}")
    return {
        "access_token": dados_sessao.get("access_token"),
        "refresh_token": dados_sessao.get("refresh_token"),
        "expires_in": dados_sessao.get("expires_in"),
        "token_type": "bearer",
    }


@router.get("/me")
async def meus_dados(request: Request):
    """Retorna dados do usuário autenticado e do seu tenant."""
    user_id: str = request.state.user_id
    tenant_id: str | None = request.state.tenant_id
    user_data: dict = request.state.user_data

    tenant = get_tenant(tenant_id) if tenant_id else None

    return {
        "id": user_id,
        "email": user_data.get("email"),
        "full_name": user_data.get("user_metadata", {}).get("full_name"),
        "tenant": tenant,
    }
