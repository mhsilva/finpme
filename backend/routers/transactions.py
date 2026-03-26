"""
Router de transações financeiras.
CRUD de lançamentos com filtros de período e categoria.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status

from db.supabase import get_supabase_client
from models.schemas import TransactionUpdate


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
async def listar_transacoes(
    request: Request,
    inicio: Optional[str] = None,
    fim: Optional[str] = None,
    categoria: Optional[str] = None,
    tipo: Optional[str] = None,  # 'entrada' | 'saida'
    pagina: int = 1,
    tamanho: int = 50,
):
    """
    Lista transações do tenant com filtros opcionais:
    - inicio / fim: período no formato YYYY-MM-DD
    - categoria: filtro por categoria
    - tipo: 'entrada' (amount > 0) ou 'saida' (amount < 0)
    """
    tenant_id: str = request.state.tenant_id
    client = get_supabase_client()

    query = (
        client.table("transactions")
        .select("*")
        .eq("tenant_id", tenant_id)
        .order("date", desc=True)
    )

    if inicio:
        query = query.gte("date", inicio)
    if fim:
        query = query.lte("date", fim)
    if categoria:
        query = query.eq("category", categoria)
    if tipo == "entrada":
        query = query.gt("amount", 0)
    elif tipo == "saida":
        query = query.lt("amount", 0)

    offset = (pagina - 1) * tamanho
    query = query.range(offset, offset + tamanho - 1)

    resultado = query.execute()
    return resultado.data or []


@router.patch("/{transaction_id}")
async def atualizar_transacao(
    transaction_id: str,
    dados: TransactionUpdate,
    request: Request,
):
    """Atualiza categoria, subcategoria ou confirmação de um lançamento."""
    tenant_id: str = request.state.tenant_id
    client = get_supabase_client()

    # Verifica se a transação pertence ao tenant
    existente = (
        client.table("transactions")
        .select("id")
        .eq("id", transaction_id)
        .eq("tenant_id", tenant_id)
        .single()
        .execute()
    )
    if not existente.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transação não encontrada",
        )

    atualizacoes = dados.model_dump(exclude_none=True)
    if not atualizacoes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum campo para atualizar",
        )

    # Se usuário está confirmando, marca como confirmado manualmente
    if "category" in atualizacoes or "dre_line" in atualizacoes:
        atualizacoes["confirmed"] = True

    resultado = (
        client.table("transactions")
        .update(atualizacoes)
        .eq("id", transaction_id)
        .execute()
    )

    logger.info(f"Transação {transaction_id} atualizada pelo tenant {tenant_id}")
    return resultado.data[0] if resultado.data else {"id": transaction_id, **atualizacoes}


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remover_transacao(transaction_id: str, request: Request):
    """Remove um lançamento financeiro."""
    tenant_id: str = request.state.tenant_id
    client = get_supabase_client()

    existente = (
        client.table("transactions")
        .select("id")
        .eq("id", transaction_id)
        .eq("tenant_id", tenant_id)
        .single()
        .execute()
    )
    if not existente.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transação não encontrada",
        )

    client.table("transactions").delete().eq("id", transaction_id).execute()
    logger.info(f"Transação {transaction_id} removida pelo tenant {tenant_id}")
