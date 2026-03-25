"""
Contas Bancárias — CRUD para registro das contas da empresa.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from db.supabase import get_supabase_client
from models.schemas import BankAccountCreate, BankAccountUpdate

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
def listar(request: Request):
    tenant_id = request.state.tenant_id
    client = get_supabase_client()
    res = (
        client.table("bank_accounts")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("active", True)
        .order("name")
        .execute()
    )
    return res.data or []


@router.post("", status_code=201)
def criar(request: Request, dados: BankAccountCreate):
    tenant_id = request.state.tenant_id
    client = get_supabase_client()
    payload = {
        "tenant_id": tenant_id,
        "name":      dados.name,
        "type":      dados.type,
        "balance":   float(dados.balance) if dados.balance is not None else 0,
    }
    if dados.bank_code:      payload["bank_code"]      = dados.bank_code
    if dados.branch:         payload["branch"]         = dados.branch
    if dados.account_number: payload["account_number"] = dados.account_number
    if dados.balance_date:   payload["balance_date"]   = dados.balance_date.isoformat()

    res = client.table("bank_accounts").insert(payload).execute()
    return res.data[0]


@router.patch("/{conta_id}")
def atualizar(conta_id: str, request: Request, dados: BankAccountUpdate):
    tenant_id = request.state.tenant_id
    client = get_supabase_client()
    update_data = dados.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")

    res = (
        client.table("bank_accounts")
        .update(update_data)
        .eq("id", conta_id)
        .eq("tenant_id", tenant_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Conta bancária não encontrada")
    return res.data[0]


@router.delete("/{conta_id}", status_code=204)
def deletar(conta_id: str, request: Request):
    tenant_id = request.state.tenant_id
    client = get_supabase_client()
    client.table("bank_accounts").update({"active": False}).eq(
        "id", conta_id
    ).eq("tenant_id", tenant_id).execute()
