"""
Centros de Custo — CRUD, rateio de transações e relatório de gastos.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from db.supabase import get_supabase_client
from models.schemas import CostCenterCreate, CostCenterUpdate

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
def listar_centros(request: Request):
    """Lista todos os centros de custo ativos do tenant."""
    tenant_id = request.state.tenant_id
    client = get_supabase_client()
    res = (
        client.table("cost_centers")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("active", True)
        .order("name")
        .execute()
    )
    return res.data or []


@router.post("/", status_code=201)
def criar_centro(request: Request, dados: CostCenterCreate):
    """Cria um novo centro de custo."""
    tenant_id = request.state.tenant_id
    client = get_supabase_client()
    payload = {
        "tenant_id": tenant_id,
        "name": dados.name,
        "code": dados.code.upper(),
        "type": dados.type,
    }
    if dados.budget is not None:
        payload["budget"] = float(dados.budget)
    if dados.parent_id is not None:
        payload["parent_id"] = str(dados.parent_id)

    res = client.table("cost_centers").insert(payload).execute()
    return res.data[0]


@router.patch("/{centro_id}")
def atualizar_centro(centro_id: str, request: Request, dados: CostCenterUpdate):
    """Atualiza campos de um centro de custo."""
    tenant_id = request.state.tenant_id
    client = get_supabase_client()
    update_data = dados.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")
    if "code" in update_data:
        update_data["code"] = update_data["code"].upper()

    res = (
        client.table("cost_centers")
        .update(update_data)
        .eq("id", centro_id)
        .eq("tenant_id", tenant_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Centro de custo não encontrado")
    return res.data[0]


@router.delete("/{centro_id}", status_code=204)
def deletar_centro(centro_id: str, request: Request):
    """Desativa (soft delete) um centro de custo."""
    tenant_id = request.state.tenant_id
    client = get_supabase_client()
    client.table("cost_centers").update({"active": False}).eq("id", centro_id).eq(
        "tenant_id", tenant_id
    ).execute()


@router.get("/{centro_id}/relatorio")
def relatorio_centro(
    centro_id: str,
    request: Request,
    inicio: str = Query(..., description="YYYY-MM-DD"),
    fim: str = Query(..., description="YYYY-MM-DD"),
):
    """Relatório de gastos de um centro de custo no período: realizado vs. orçamento."""
    tenant_id = request.state.tenant_id
    client = get_supabase_client()

    # Busca o CC
    cc_res = (
        client.table("cost_centers")
        .select("*")
        .eq("id", centro_id)
        .eq("tenant_id", tenant_id)
        .single()
        .execute()
    )
    if not cc_res.data:
        raise HTTPException(status_code=404, detail="Centro de custo não encontrado")
    cc = cc_res.data

    # Busca alocações com a transação relacionada
    aloc_res = (
        client.table("transaction_cost_centers")
        .select("amount, percentage, transaction_id, transactions(date, description, category, amount)")
        .eq("tenant_id", tenant_id)
        .eq("cost_center_id", centro_id)
        .execute()
    )
    alocacoes = aloc_res.data or []

    # Filtra por período em Python (PostgREST não suporta filtro em embedded table diretamente)
    filtradas = [
        a for a in alocacoes
        if a.get("transactions") and inicio <= a["transactions"]["date"] <= fim
    ]

    total_gasto = sum(abs(float(a["amount"])) for a in filtradas)
    orcamento = float(cc.get("budget") or 0)

    return {
        "centro": cc,
        "periodo": {"inicio": inicio, "fim": fim},
        "total_gasto": round(total_gasto, 2),
        "orcamento": orcamento,
        "utilizacao_pct": round((total_gasto / orcamento * 100) if orcamento > 0 else 0, 1),
        "lancamentos": [
            {
                "data": a["transactions"]["date"],
                "descricao": a["transactions"]["description"],
                "categoria": a["transactions"].get("category"),
                "valor": round(abs(float(a["amount"])), 2),
                "percentual": float(a["percentage"]),
            }
            for a in sorted(filtradas, key=lambda x: x["transactions"]["date"], reverse=True)
        ],
    }


@router.post("/transacao/{transaction_id}", status_code=201)
def alocar_transacao(
    transaction_id: str,
    request: Request,
    cost_center_id: str = Query(...),
    percentage: float = Query(100.0, ge=1, le=100),
):
    """Aloca uma transação a um centro de custo (substitui alocação anterior)."""
    tenant_id = request.state.tenant_id
    client = get_supabase_client()

    tx_res = (
        client.table("transactions")
        .select("id, amount")
        .eq("id", transaction_id)
        .eq("tenant_id", tenant_id)
        .single()
        .execute()
    )
    if not tx_res.data:
        raise HTTPException(status_code=404, detail="Transação não encontrada")

    amount = float(tx_res.data["amount"]) * (percentage / 100)

    # Remove alocações anteriores e insere a nova
    client.table("transaction_cost_centers").delete().eq(
        "transaction_id", transaction_id
    ).eq("tenant_id", tenant_id).execute()

    res = (
        client.table("transaction_cost_centers")
        .insert({
            "tenant_id": tenant_id,
            "transaction_id": transaction_id,
            "cost_center_id": cost_center_id,
            "percentage": percentage,
            "amount": amount,
        })
        .execute()
    )
    return res.data[0]


@router.delete("/transacao/{transaction_id}", status_code=204)
def remover_alocacao(transaction_id: str, request: Request):
    """Remove a alocação de uma transação."""
    tenant_id = request.state.tenant_id
    client = get_supabase_client()
    client.table("transaction_cost_centers").delete().eq(
        "transaction_id", transaction_id
    ).eq("tenant_id", tenant_id).execute()
