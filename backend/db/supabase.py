"""
Cliente Supabase e funções de acesso ao banco de dados.
"""

import logging
import os
from functools import lru_cache
from typing import Optional
from uuid import UUID

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """Retorna instância singleton do cliente Supabase (service role)."""
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def get_tenant_id(user_id: str) -> Optional[str]:
    """
    Busca o tenant_id associado ao usuário.
    Retorna None se o usuário não estiver vinculado a nenhum tenant.
    """
    client = get_supabase_client()
    try:
        result = (
            client.table("tenant_users")
            .select("tenant_id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]["tenant_id"]
        return None
    except Exception as e:
        logger.error(f"Erro ao buscar tenant_id para usuário {user_id}: {e}")
        return None


def get_tenant(tenant_id: str) -> Optional[dict]:
    """Retorna os dados do tenant pelo ID."""
    client = get_supabase_client()
    try:
        result = (
            client.table("tenants")
            .select("*")
            .eq("id", tenant_id)
            .single()
            .execute()
        )
        return result.data
    except Exception as e:
        logger.error(f"Erro ao buscar tenant {tenant_id}: {e}")
        return None


def create_tenant(name: str, cnpj: Optional[str] = None, tax_regime: str = "simples") -> dict:
    """Cria um novo tenant (empresa) no banco."""
    client = get_supabase_client()
    result = (
        client.table("tenants")
        .insert({"name": name, "cnpj": cnpj, "tax_regime": tax_regime})
        .execute()
    )
    return result.data[0]


def create_tenant_user(tenant_id: str, user_id: str, role: str = "owner") -> dict:
    """Vincula um usuário a um tenant com um papel específico."""
    client = get_supabase_client()
    result = (
        client.table("tenant_users")
        .insert({"tenant_id": tenant_id, "user_id": user_id, "role": role})
        .execute()
    )
    return result.data[0]


def get_chart_of_accounts(tenant_id: str) -> list[dict]:
    """Retorna o plano de contas do tenant."""
    client = get_supabase_client()
    result = (
        client.table("chart_of_accounts")
        .select("*")
        .eq("tenant_id", tenant_id)
        .order("code")
        .execute()
    )
    return result.data or []
