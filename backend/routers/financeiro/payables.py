"""
Contas a Pagar e Receber — CRUD, parcelamento e controle de vencimentos.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from db.supabase import get_supabase_client
from models.schemas import PayableReceivableCreate, PayableReceivableUpdate

logger = logging.getLogger(__name__)
router = APIRouter()


def _marcar_vencidas(tenant_id: str):
    """Atualiza para 'overdue' todas as contas pendentes com vencimento passado."""
    client = get_supabase_client()
    hoje = date.today().isoformat()
    client.table("payables_receivables").update({"status": "overdue"}).eq(
        "tenant_id", tenant_id
    ).eq("status", "pending").lt("due_date", hoje).execute()


@router.get("/")
def listar_contas(
    request: Request,
    type: Optional[str] = Query(None, description="payable | receivable"),
    status: Optional[str] = Query(None, description="pending | paid | overdue | partial | cancelled"),
    inicio: Optional[str] = Query(None),
    fim: Optional[str] = Query(None),
    limite: int = Query(100, le=500),
):
    """Lista contas a pagar/receber com filtros. Auto-atualiza vencidos."""
    tenant_id = request.state.tenant_id
    _marcar_vencidas(tenant_id)

    client = get_supabase_client()
    query = (
        client.table("payables_receivables")
        .select("*")
        .eq("tenant_id", tenant_id)
        .order("due_date")
        .limit(limite)
    )
    if type:
        query = query.eq("type", type)
    if status:
        query = query.eq("status", status)
    if inicio:
        query = query.gte("due_date", inicio)
    if fim:
        query = query.lte("due_date", fim)

    res = query.execute()
    return res.data or []


@router.get("/resumo")
def resumo_contas(request: Request):
    """Totais de a pagar, a receber e vencidos para o dashboard."""
    tenant_id = request.state.tenant_id
    _marcar_vencidas(tenant_id)

    client = get_supabase_client()
    hoje = date.today().isoformat()

    res = (
        client.table("payables_receivables")
        .select("type, status, amount")
        .eq("tenant_id", tenant_id)
        .neq("status", "cancelled")
        .execute()
    )
    contas = res.data or []

    a_pagar   = sum(float(c["amount"]) for c in contas if c["type"] == "payable"    and c["status"] in ("pending", "overdue", "partial"))
    a_receber = sum(float(c["amount"]) for c in contas if c["type"] == "receivable" and c["status"] in ("pending", "overdue", "partial"))
    vencidos  = sum(float(c["amount"]) for c in contas if c["status"] == "overdue")

    return {
        "a_pagar":   round(a_pagar, 2),
        "a_receber": round(a_receber, 2),
        "vencidos":  round(vencidos, 2),
        "saldo_previsto": round(a_receber - a_pagar, 2),
    }


@router.post("/", status_code=201)
def criar_conta(request: Request, dados: PayableReceivableCreate):
    """
    Cria conta(s) a pagar/receber.
    Se installments_total > 1, gera N parcelas automaticamente.
    """
    tenant_id = request.state.tenant_id
    client = get_supabase_client()

    n = dados.installments_total
    valor_parcela = round(float(dados.amount) / n, 2)
    # Ajusta última parcela para cobrir diferença de arredondamento
    valor_ultima = round(float(dados.amount) - valor_parcela * (n - 1), 2)

    registros = []
    parent_id = None

    for i in range(n):
        parcela_num = i + 1
        # Calcula vencimento: mensal por padrão para parcelamentos
        if dados.recurrence == "weekly":
            due = dados.due_date + timedelta(weeks=i)
        elif dados.recurrence == "yearly":
            due = dados.due_date.replace(year=dados.due_date.year + i)
        else:
            # mensal — avança mês a mês
            mes = dados.due_date.month + i
            ano = dados.due_date.year + (mes - 1) // 12
            mes = ((mes - 1) % 12) + 1
            ultimo_dia = (date(ano, mes % 12 + 1, 1) - timedelta(days=1)).day if mes < 12 else 31
            dia = min(dados.due_date.day, ultimo_dia)
            due = date(ano, mes, dia)

        payload: dict = {
            "tenant_id":         tenant_id,
            "type":              dados.type,
            "description":       dados.description if n == 1 else f"{dados.description} ({parcela_num}/{n})",
            "amount":            valor_parcela if parcela_num < n else valor_ultima,
            "due_date":          due.isoformat(),
            "status":            "pending",
            "contact_name":      dados.contact_name,
            "contact_doc":       dados.contact_doc,
            "installments_total": n,
            "installments_num":  parcela_num,
            "notes":             dados.notes,
        }
        if dados.recurrence and n == 1:
            payload["recurrence"] = dados.recurrence
        if dados.bank_account_id:
            payload["bank_account_id"] = str(dados.bank_account_id)
        if dados.cost_center_id:
            payload["cost_center_id"] = str(dados.cost_center_id)
        if parent_id:
            payload["parent_id"] = parent_id

        res = client.table("payables_receivables").insert(payload).execute()
        criado = res.data[0]

        # Primeira parcela vira parent das demais
        if i == 0 and n > 1:
            parent_id = criado["id"]
            client.table("payables_receivables").update({"parent_id": parent_id}).eq(
                "id", parent_id
            ).execute()
            criado["parent_id"] = parent_id

        registros.append(criado)

    return registros[0] if n == 1 else {"parcelas": len(registros), "registros": registros}


@router.patch("/{conta_id}")
def atualizar_conta(conta_id: str, request: Request, dados: PayableReceivableUpdate):
    """Atualiza campos de uma conta."""
    tenant_id = request.state.tenant_id
    client = get_supabase_client()
    update_data = dados.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")

    res = (
        client.table("payables_receivables")
        .update(update_data)
        .eq("id", conta_id)
        .eq("tenant_id", tenant_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    return res.data[0]


@router.post("/{conta_id}/pagar")
def marcar_pago(
    conta_id: str,
    request: Request,
    paid_date: Optional[str] = Query(None, description="YYYY-MM-DD (padrão: hoje)"),
    transaction_id: Optional[str] = Query(None, description="UUID da transação bancária para conciliação"),
    valor_pago: Optional[float] = Query(None, description="Se diferente do total, marca como 'partial'"),
):
    """Marca uma conta como paga, com data e link opcional à transação bancária."""
    tenant_id = request.state.tenant_id
    client = get_supabase_client()

    conta_res = (
        client.table("payables_receivables")
        .select("amount, status")
        .eq("id", conta_id)
        .eq("tenant_id", tenant_id)
        .single()
        .execute()
    )
    if not conta_res.data:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    conta = conta_res.data

    if conta["status"] in ("cancelled",):
        raise HTTPException(status_code=400, detail="Conta cancelada não pode ser marcada como paga")

    data_pagamento = paid_date or date.today().isoformat()
    novo_status = "paid"
    if valor_pago is not None and round(valor_pago, 2) < round(float(conta["amount"]), 2):
        novo_status = "partial"

    update: dict = {"status": novo_status, "paid_date": data_pagamento}
    if transaction_id:
        update["transaction_id"] = transaction_id

    res = (
        client.table("payables_receivables")
        .update(update)
        .eq("id", conta_id)
        .eq("tenant_id", tenant_id)
        .execute()
    )
    return res.data[0]


@router.delete("/{conta_id}", status_code=204)
def cancelar_conta(
    conta_id: str,
    request: Request,
    todas_parcelas: bool = Query(False, description="Cancela todas as parcelas do mesmo parcelamento"),
):
    """Cancela (soft delete via status) uma conta ou todas as suas parcelas."""
    tenant_id = request.state.tenant_id
    client = get_supabase_client()

    if todas_parcelas:
        # Busca parent_id para cancelar o grupo inteiro
        res = (
            client.table("payables_receivables")
            .select("parent_id")
            .eq("id", conta_id)
            .eq("tenant_id", tenant_id)
            .single()
            .execute()
        )
        if res.data:
            parent_id = res.data.get("parent_id") or conta_id
            client.table("payables_receivables").update({"status": "cancelled"}).eq(
                "tenant_id", tenant_id
            ).eq("parent_id", parent_id).neq("status", "paid").execute()
            # Cancela o próprio parent também
            client.table("payables_receivables").update({"status": "cancelled"}).eq(
                "id", parent_id
            ).eq("tenant_id", tenant_id).execute()
        return

    client.table("payables_receivables").update({"status": "cancelled"}).eq(
        "id", conta_id
    ).eq("tenant_id", tenant_id).execute()
